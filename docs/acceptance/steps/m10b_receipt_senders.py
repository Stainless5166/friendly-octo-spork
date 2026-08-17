"""Real step bindings for the known-sender registry + deterministic
extractor module (spork.core.receipts.registry/extract).

Fully implemented, unlike m10_receipt_archiving.feature (still @wip).
Uses a real StateDB (a fresh tmp-path file per scenario) and a small
fake domain_lookup collaborator, no live account or network.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from behave import given, then, when

from spork.core.models import NormalizedMessage
from spork.core.receipts.extract import extract_receipt
from spork.core.receipts.registry import normalize_sender_domain
from spork.core.state.db import StateDB


@dataclass(frozen=True, slots=True)
class _FakeDomainRecord:
    company: str | None


class _FakeDomainLookup:
    """Stands in for EntityContextProvider.lookup_domain() (M9)."""

    def __init__(self) -> None:
        self._domains: dict[str, str] = {}

    def seed(self, domain: str, company: str) -> None:
        self._domains[normalize_sender_domain(domain)] = company

    def lookup_domain(self, domain: str) -> _FakeDomainRecord | None:
        company = self._domains.get(normalize_sender_domain(domain))
        return _FakeDomainRecord(company=company) if company else None


def _state_db(context: Any) -> StateDB:
    if not hasattr(context, "state_db"):
        db_path = Path(tempfile.mkdtemp(prefix="spork-m10b-acceptance-")) / "state.sqlite3"
        context.state_db = StateDB(db_path)
    db: StateDB = context.state_db
    return db


def _domain_lookup(context: Any) -> _FakeDomainLookup:
    if not hasattr(context, "domain_lookup"):
        context.domain_lookup = _FakeDomainLookup()
    lookup: _FakeDomainLookup = context.domain_lookup
    return lookup


def _message_from(domain: str, *, with_date: bool) -> NormalizedMessage:
    headers = {"Date": "Sat, 01 Aug 2026 00:00:00 +0000"} if with_date else {}
    return NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address=f"billing@{domain}",
        from_domain=domain,
        subject="Your receipt",
        body_text="Thanks for your payment.",
        headers=headers,
    )


@given('"{domain}" was learned as "{company}" in the registry')
def domain_was_learned(context: Any, domain: str, company: str) -> None:
    _state_db(context).learn_known_sender(
        normalize_sender_domain(domain), company=company, learned_from="seed", learned_at="t0"
    )


@given('a curated domain lookup resolves "{domain}" to "{company}"')
def curated_domain_lookup_resolves(context: Any, domain: str, company: str) -> None:
    _domain_lookup(context).seed(domain, company)


def _extract(context: Any, domain: str) -> None:
    known_sender = _state_db(context).get_known_sender(normalize_sender_domain(domain))
    context.extraction = extract_receipt(
        context.message, known_sender=known_sender, domain_lookup=_domain_lookup(context)
    )


@when('a receipt message from "{domain}" with a Date header is extracted')
def message_with_date_extracted(context: Any, domain: str) -> None:
    context.message = _message_from(domain, with_date=True)
    _extract(context, domain)


@when('a second receipt message from "{domain}" with a Date header is extracted')
def second_message_with_date_extracted(context: Any, domain: str) -> None:
    message_with_date_extracted(context, domain)


@when('a receipt message from "{domain}" with no date anywhere is extracted')
def message_with_no_date_extracted(context: Any, domain: str) -> None:
    context.message = _message_from(domain, with_date=False)
    _extract(context, domain)


@when('"{domain}" is learned as "{company}" in the registry')
def learn_domain(context: Any, domain: str, company: str) -> None:
    _state_db(context).learn_known_sender(
        normalize_sender_domain(domain), company=company, learned_from="tier2", learned_at="t1"
    )


@then('the extraction succeeds with company "{company}"')
def extraction_succeeds_with_company(context: Any, company: str) -> None:
    assert context.extraction is not None, "expected an extraction, got a decline"
    assert context.extraction.company == company


@then("the extraction declines")
def extraction_declines(context: Any) -> None:
    assert context.extraction is None, f"expected a decline, got {context.extraction!r}"
