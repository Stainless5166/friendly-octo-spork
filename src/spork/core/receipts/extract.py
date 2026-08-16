"""The deterministic company/date extraction path (docs/DESIGN.md §9.5).

Checked in two layers before ever escalating to Tier 2: an optional
`domain_lookup` collaborator (structurally matching
`EntityContextProvider.lookup_domain()`, M9's curated, read-only
domain->company data — reused here rather than this milestone
inventing a second static-seed-file format) first, then a
StateDB-sourced `KnownSender` (this milestone's own learned cache)
second. Either half missing -- no company, or no date -- means
`extract_receipt()` declines (returns `None`) rather than guessing;
that's what routes a message to the one narrow Tier 2 fallback call
instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from spork.core.models import NormalizedMessage
from spork.core.state.db import KnownSender

# Deliberately not a general date-in-any-format parser -- same "closed,
# auditable pattern set" philosophy as rules.schema.Condition (§7.5).
# The Date header (checked separately, first) covers the common case;
# these cover receipts that state their own invoice/payment date
# explicitly in the body, which is the more trustworthy value when
# both are present but this module only reaches the body when there's
# no Date header at all.
_BODY_DATE_PATTERNS = [
    re.compile(r"(?:Invoice|Payment|Receipt) date:\s*(\S.*)", re.IGNORECASE),
]


@dataclass(frozen=True, slots=True)
class ReceiptExtraction:
    """A resolved company + date pair, ready for tagging/archiving."""

    company: str
    date: str


class _DomainRecord(Protocol):
    """Structurally matches `spork.core.context.clients.entities.models.Domain`
    (and anything else shaped like it) without importing `spork.core.context`
    -- a narrow, purpose-built Protocol for the one attribute this module
    actually reads."""

    company: str | None


@runtime_checkable
class SenderDomainLookup(Protocol):
    """Structurally matches `EntityContextProvider.lookup_domain()`.

    Deliberately not a dependency on `spork.core.context.base.ContextProvider`
    (that Protocol's `get_context()` returns free-text `ContextSnippet`s
    for a Tier 2 prompt, not a structured company) -- this is its own
    narrow relationship, the same "one Protocol per real relationship"
    call `ThreadHistoryReader`/`MailboxLister`/`MessageLookup` already
    made (§9.3). `@runtime_checkable` (same as `CheckpointedProvider`/
    `BackfillProvider`, §9.3) lets `spork.core.runtime` ask "does the
    configured `ContextProvider` happen to also support this?" via a
    plain `isinstance()` check, rather than hard-coding a dependency on
    the concrete `EntityContextProvider` class.
    """

    def lookup_domain(self, domain: str) -> _DomainRecord | None: ...


def extract_date(message: NormalizedMessage) -> str | None:
    """Resolve a receipt's date from a closed set of sources: the
    `Date` header first (present on every real email, and receipts are
    overwhelmingly sent same-day as the charge), then a short list of
    literal body markers."""
    header_date = message.headers.get("Date")
    if header_date:
        return header_date.strip()
    for pattern in _BODY_DATE_PATTERNS:
        match = pattern.search(message.body_text)
        if match:
            return match.group(1).strip()
    return None


def resolve_company(
    from_domain: str,
    *,
    known_sender: KnownSender | None,
    domain_lookup: SenderDomainLookup | None = None,
) -> str | None:
    """Resolve `from_domain` to a company, curated data first.

    A `domain_lookup` hit with no `company` recorded (a real,
    documented `Domain` state — a domain tracked with no owning
    company yet) falls through to `known_sender` rather than being
    treated as a match; only a company name naturally continues.
    """
    if domain_lookup is not None:
        record = domain_lookup.lookup_domain(from_domain)
        if record is not None and record.company:
            return record.company
    if known_sender is not None:
        return known_sender.company
    return None


def extract_receipt(
    message: NormalizedMessage,
    *,
    known_sender: KnownSender | None,
    domain_lookup: SenderDomainLookup | None = None,
) -> ReceiptExtraction | None:
    """Resolve company and date deterministically, or decline.

    Declining (returning `None`) is what routes a message to the one
    narrow Tier 2 extraction fallback (`spork.core.receipts.llm`) —
    this function never guesses a partial answer.
    """
    company = resolve_company(
        message.from_domain, known_sender=known_sender, domain_lookup=domain_lookup
    )
    if company is None:
        return None
    date = extract_date(message)
    if date is None:
        return None
    return ReceiptExtraction(company=company, date=date)
