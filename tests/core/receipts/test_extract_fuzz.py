"""Property-based tests for spork.core.receipts.extract (docs/DESIGN.md §16.1).

Companion to test_extract.py's example-based tests. extract_receipt()'s
whole contract is a decline-rather-than-guess chain (domain_lookup, then
known_sender, then a closed date-pattern set) — stated here as
invariants over Hypothesis-generated companies/dates/messages rather
than the one hand-picked sender/date pair each example test uses.
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import given
from hypothesis import strategies as st

from spork.core.models import NormalizedMessage
from spork.core.receipts.extract import extract_date, extract_receipt, resolve_company
from spork.core.state.db import KnownSender

# Non-empty text stands in for a company name / date string / domain —
# extract_receipt() never validates these beyond truthiness, so their
# exact shape shouldn't matter to any property here.
_NONEMPTY = st.text(min_size=1, max_size=20)


@dataclass(frozen=True, slots=True)
class _FakeDomainRecord:
    company: str | None


class _FakeDomainLookup:
    """Stands in for EntityContextProvider without importing spork.core.context —
    same fake test_extract.py already uses."""

    def __init__(self, company: str | None) -> None:
        self._company = company

    def lookup_domain(self, domain: str) -> _FakeDomainRecord:
        return _FakeDomainRecord(company=self._company)


@st.composite
def _messages(draw: st.DrawFn, *, headers: dict[str, str] | None = None) -> NormalizedMessage:
    """An arbitrary NormalizedMessage; headers/body_text overridable per
    test so each property only varies the field it's actually about."""
    return NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address=draw(_NONEMPTY),
        from_domain=draw(_NONEMPTY),
        subject=draw(st.text(max_size=20)),
        body_text=draw(st.text(max_size=40)),
        headers=headers if headers is not None else {},
    )


@given(
    domain_lookup_company=_NONEMPTY,
    known_sender_company=_NONEMPTY,
    from_domain=_NONEMPTY,
)
def test_domain_lookup_company_always_wins_over_known_sender(
    domain_lookup_company: str, known_sender_company: str, from_domain: str
) -> None:
    """For any two distinct, non-empty company strings, a domain_lookup
    hit with a real company always resolves ahead of known_sender —
    generalizes test_extract.py's one hand-picked pair to any input
    Hypothesis generates."""
    known_sender = KnownSender(
        from_domain=from_domain,
        company=known_sender_company,
        learned_from="tier2",
        learned_at="t0",
    )

    resolved = resolve_company(
        from_domain,
        known_sender=known_sender,
        domain_lookup=_FakeDomainLookup(domain_lookup_company),
    )

    assert resolved == domain_lookup_company


@given(known_sender_company=_NONEMPTY, from_domain=_NONEMPTY)
def test_domain_lookup_hit_with_no_company_always_falls_through(
    known_sender_company: str, from_domain: str
) -> None:
    """A domain_lookup hit that carries no company (a real, documented
    Domain state) always falls through to known_sender — for any
    known_sender.company Hypothesis generates, never treated as a match
    itself."""
    known_sender = KnownSender(
        from_domain=from_domain,
        company=known_sender_company,
        learned_from="seed",
        learned_at="t0",
    )

    resolved = resolve_company(
        from_domain, known_sender=known_sender, domain_lookup=_FakeDomainLookup(None)
    )

    assert resolved == known_sender_company


@given(message=_messages())
def test_no_known_sender_and_no_domain_lookup_always_declines(message: NormalizedMessage) -> None:
    """Company resolution is the first gate: with neither collaborator
    supplied, extract_receipt() declines for any message Hypothesis
    generates, regardless of what Date header or body text it carries."""
    assert extract_receipt(message, known_sender=None, domain_lookup=None) is None


@given(header_date=_NONEMPTY, body_text=st.text(max_size=40))
def test_extract_date_always_prefers_a_present_date_header(
    header_date: str, body_text: str
) -> None:
    """Any non-empty Date header wins over body markers, for any body
    text Hypothesis generates alongside it — the header is checked
    first and short-circuits the body-pattern scan entirely."""
    message = NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address="a@example.com",
        from_domain="example.com",
        subject="",
        body_text=body_text,
        headers={"Date": header_date},
    )

    assert extract_date(message) == header_date.strip()


@given(message=_messages(headers={}))
def test_extract_receipt_result_always_matches_its_own_helpers(
    message: NormalizedMessage,
) -> None:
    """Oracle cross-check: whenever extract_receipt() returns a result,
    its company/date fields are exactly what resolve_company()/
    extract_date() independently compute for the same inputs — the
    combining function never transforms either half."""
    known_sender = KnownSender(
        from_domain=message.from_domain, company="Acme", learned_from="seed", learned_at="t0"
    )

    result = extract_receipt(message, known_sender=known_sender)

    expected_company = resolve_company(message.from_domain, known_sender=known_sender)
    expected_date = extract_date(message)
    if expected_company is None or expected_date is None:
        assert result is None
    else:
        assert result is not None
        assert result.company == expected_company
        assert result.date == expected_date
