"""Acceptance tests for spork.core.receipts.registry (docs/DESIGN.md §9.5).

normalize_sender_domain() is the pure logic half of the known-sender
registry -- storage itself lives on StateDB (get_known_sender/
learn_known_sender, see tests/core/state/test_db_known_senders.py),
mirroring how spork.core.llm.budget.has_budget_remaining() is pure
logic decoupled from StateDB.get_llm_usage().
"""

from __future__ import annotations

from spork.core.receipts.registry import normalize_sender_domain


def test_lowercases_a_mixed_case_domain() -> None:
    assert normalize_sender_domain("BillING.AcmeCloud.com") == "billing.acmecloud.com"


def test_strips_surrounding_whitespace() -> None:
    assert normalize_sender_domain("  acmecloud.com  ") == "acmecloud.com"


def test_already_normalized_domain_is_unchanged() -> None:
    assert normalize_sender_domain("acmecloud.com") == "acmecloud.com"


def test_a_learned_domain_is_found_regardless_of_the_lookup_domain_casing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from spork.core.state.db import StateDB

    with StateDB(tmp_path / "state.sqlite3") as db:
        db.learn_known_sender(
            normalize_sender_domain("Billing.AcmeCloud.com"),
            company="Acme Cloud",
            learned_from="seed",
            learned_at="t0",
        )

        assert db.get_known_sender(normalize_sender_domain("BILLING.acmecloud.COM")) is not None
