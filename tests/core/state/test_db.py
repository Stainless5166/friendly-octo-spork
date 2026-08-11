"""Acceptance tests for the persistent state store (docs/DESIGN.md §7.4).

Uses a real SQLite file under pytest's tmp_path — this is spork's own
schema/query logic under test, not sqlite3's own correctness.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.state.db import StateDB


def test_set_and_get_cursor_roundtrips(tmp_path: Path) -> None:
    """A cursor set for an account is exactly what get_cursor returns."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.set_cursor("account-1", "state-abc123")

        assert db.get_cursor("account-1") == "state-abc123"


def test_get_cursor_returns_none_when_never_set(tmp_path: Path) -> None:
    """An account with no recorded cursor is "never polled", not an error."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        assert db.get_cursor("never-seen-account") is None


def test_set_cursor_overwrites_previous_value(tmp_path: Path) -> None:
    """Setting a new cursor for an account replaces the old one — this
    is how a running daemon advances its position after each fetch."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.set_cursor("account-1", "state-1")
        db.set_cursor("account-1", "state-2")

        assert db.get_cursor("account-1") == "state-2"


def test_has_processed_is_false_for_unknown_message(tmp_path: Path) -> None:
    """A message never marked processed is correctly reported as new."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        assert db.has_processed("msg-1") is False


def test_mark_processed_then_has_processed_is_true(tmp_path: Path) -> None:
    """The idempotency check the action executor (M2) will consult
    before acting on a message: once marked, has_processed is True."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.mark_processed("msg-1", thread_id="thread-1", processed_at="2026-08-11T00:00:00Z")

        assert db.has_processed("msg-1") is True


def test_schema_is_created_on_a_fresh_db_file(tmp_path: Path) -> None:
    """Opening StateDB against a path that doesn't exist yet creates the
    schema automatically — no separate "init" step required."""
    db_path = tmp_path / "does-not-exist-yet.sqlite3"
    assert not db_path.exists()

    with StateDB(db_path) as db:
        db.set_cursor("account-1", "state-1")

    assert db_path.exists()
