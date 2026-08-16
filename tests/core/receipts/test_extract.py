"""Acceptance tests for spork.core.receipts.extract (docs/DESIGN.md §9.5).

The deterministic path: an optional domain_lookup collaborator
(structurally matching EntityContextProvider.lookup_domain(), M9,
checked first) or a StateDB-sourced KnownSender (checked second)
resolves company; a closed set of date patterns resolves date. Either
half missing means extract_receipt() declines (returns None) rather
than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass

from spork.core.models import NormalizedMessage
from spork.core.receipts.extract import ReceiptExtraction, extract_receipt
from spork.core.state.db import KnownSender


@dataclass(frozen=True, slots=True)
class _FakeDomainRecord:
    company: str | None


class _FakeDomainLookup:
    """Stands in for EntityContextProvider without importing spork.core.context."""

    def __init__(self, domains: dict[str, str | None]) -> None:
        self._domains = domains

    def lookup_domain(self, domain: str) -> _FakeDomainRecord | None:
        if domain not in self._domains:
            return None
        return _FakeDomainRecord(company=self._domains[domain])


def _message(**overrides: object) -> NormalizedMessage:
    defaults: dict[str, object] = {
        "message_id": "msg-1",
        "thread_id": "thread-1",
        "from_address": "billing@acmecloud.com",
        "from_domain": "acmecloud.com",
        "subject": "Your Acme Cloud receipt",
        "body_text": "Thanks for your payment.",
        "headers": {},
    }
    defaults.update(overrides)
    return NormalizedMessage(**defaults)  # type: ignore[arg-type]


def test_known_sender_plus_date_header_produces_an_extraction() -> None:
    known_sender = KnownSender(
        from_domain="acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
    )
    message = _message(headers={"Date": "Sat, 01 Aug 2026 00:00:00 +0000"})

    result = extract_receipt(message, known_sender=known_sender)

    assert result == ReceiptExtraction(company="Acme Cloud", date="Sat, 01 Aug 2026 00:00:00 +0000")


def test_domain_lookup_is_checked_before_and_wins_over_known_sender() -> None:
    known_sender = KnownSender(
        from_domain="acmecloud.com", company="Wrong Name", learned_from="seed", learned_at="t0"
    )
    domain_lookup = _FakeDomainLookup({"acmecloud.com": "Acme Cloud (curated)"})
    message = _message(headers={"Date": "2026-08-01"})

    result = extract_receipt(message, known_sender=known_sender, domain_lookup=domain_lookup)

    assert result is not None
    assert result.company == "Acme Cloud (curated)"


def test_falls_back_to_known_sender_when_domain_lookup_has_no_match() -> None:
    known_sender = KnownSender(
        from_domain="acmecloud.com", company="Acme Cloud", learned_from="tier2", learned_at="t0"
    )
    domain_lookup = _FakeDomainLookup({})  # nothing tracked
    message = _message(headers={"Date": "2026-08-01"})

    result = extract_receipt(message, known_sender=known_sender, domain_lookup=domain_lookup)

    assert result is not None
    assert result.company == "Acme Cloud"


def test_domain_lookup_hit_with_no_company_falls_back_to_known_sender() -> None:
    """A tracked Domain with no owning company recorded (a real,
    documented state in EntityContextProvider's own model) isn't a
    usable company -- fall through, don't treat it as found."""
    known_sender = KnownSender(
        from_domain="acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
    )
    domain_lookup = _FakeDomainLookup({"acmecloud.com": None})
    message = _message(headers={"Date": "2026-08-01"})

    result = extract_receipt(message, known_sender=known_sender, domain_lookup=domain_lookup)

    assert result is not None
    assert result.company == "Acme Cloud"


def test_no_known_sender_and_no_domain_lookup_match_declines() -> None:
    message = _message(headers={"Date": "2026-08-01"})

    assert extract_receipt(message, known_sender=None) is None


def test_company_resolved_but_no_date_anywhere_declines() -> None:
    known_sender = KnownSender(
        from_domain="acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
    )
    message = _message(headers={}, body_text="Thanks for your business.")

    assert extract_receipt(message, known_sender=known_sender) is None


def test_falls_back_to_a_body_date_marker_when_no_date_header() -> None:
    known_sender = KnownSender(
        from_domain="acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
    )
    message = _message(
        headers={}, body_text="Thank you.\nInvoice date: 2026-08-01\nAmount: $12.00"
    )

    result = extract_receipt(message, known_sender=known_sender)

    assert result is not None
    assert result.date == "2026-08-01"
