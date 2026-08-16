"""Acceptance tests for StateDB's known_receipt_senders table (docs/DESIGN.md §9.5, M9).

Companion to test_db.py, split into its own file rather than appended
there since this is a distinct feature area (receipt archiving's
"learning system") added well after M1's original two tables — same
reasoning llm_usage's tests get their own grouping.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.state.db import StateDB


def test_get_known_sender_returns_none_when_never_learned(tmp_path: Path) -> None:
    with StateDB(tmp_path / "state.sqlite3") as db:
        assert db.get_known_sender("newvendor.io") is None


def test_learn_known_sender_then_get_known_sender_roundtrips(tmp_path: Path) -> None:
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.learn_known_sender(
            "newvendor.io",
            company="New Vendor Inc",
            learned_from="tier2",
            learned_at="2026-08-16T00:00:00Z",
        )

        sender = db.get_known_sender("newvendor.io")
        assert sender is not None
        assert sender.from_domain == "newvendor.io"
        assert sender.company == "New Vendor Inc"
        assert sender.learned_from == "tier2"
        assert sender.learned_at == "2026-08-16T00:00:00Z"


def test_learn_known_sender_overwrites_a_previous_entry_for_the_same_domain(
    tmp_path: Path,
) -> None:
    """Re-learning a domain (e.g. a corrected company name) replaces the
    old row rather than erroring or duplicating it."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.learn_known_sender(
            "newvendor.io", company="New Vendor", learned_from="tier2", learned_at="t1"
        )
        db.learn_known_sender(
            "newvendor.io", company="New Vendor Inc", learned_from="tier2", learned_at="t2"
        )

        sender = db.get_known_sender("newvendor.io")
        assert sender is not None
        assert sender.company == "New Vendor Inc"
        assert sender.learned_at == "t2"


def test_seeded_and_learned_senders_are_both_stored_the_same_way(tmp_path: Path) -> None:
    """learned_from distinguishes a hand-authored seed from a Tier 2
    extraction, but both are ordinary rows -- no separate table or
    lookup path for either."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.learn_known_sender(
            "acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
        )
        db.learn_known_sender(
            "newvendor.io", company="New Vendor Inc", learned_from="tier2", learned_at="t1"
        )

        seeded = db.get_known_sender("acmecloud.com")
        learned = db.get_known_sender("newvendor.io")
        assert seeded is not None and seeded.learned_from == "seed"
        assert learned is not None and learned.learned_from == "tier2"


def test_known_senders_persist_across_reconnecting_to_the_same_db_file(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    with StateDB(db_path) as db:
        db.learn_known_sender(
            "acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
        )

    with StateDB(db_path) as db:
        sender = db.get_known_sender("acmecloud.com")
        assert sender is not None
        assert sender.company == "Acme Cloud"
