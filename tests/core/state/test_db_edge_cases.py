"""Failure/edge-case tests for the persistent state store.

Companion to test_db.py's acceptance tests.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from spork.core.state.db import StateDB


def test_mark_processed_twice_updates_the_record(tmp_path: Path) -> None:
    """Re-marking an already-processed message overwrites its stored
    outcome rather than erroring — the reclassify (M5) use case."""
    db_path = tmp_path / "state.sqlite3"
    with StateDB(db_path) as db:
        db.mark_processed(
            "msg-1",
            thread_id="thread-1",
            processed_at="2026-08-11T00:00:00Z",
            action_taken="move:Reading",
        )
        db.mark_processed(
            "msg-1",
            thread_id="thread-1",
            processed_at="2026-08-11T01:00:00Z",
            action_taken="move:Urgent",
        )

    # Verify via a fresh connection rather than StateDB's own internals
    # — this checks what actually landed on disk, not an implementation
    # detail of how StateDB got it there.
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT action_taken, processed_at FROM processed_messages WHERE jmap_id = ?",
        ("msg-1",),
    ).fetchone()
    conn.close()

    assert row == ("move:Urgent", "2026-08-11T01:00:00Z")


def test_multiple_accounts_have_independent_push_cursors(tmp_path: Path) -> None:
    """Cursors are keyed per account_id — setting one account's cursor
    must not affect another's (a future multi-profile config shouldn't
    have to worry about cursors bleeding across accounts)."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.set_cursor("account-1", "state-a")
        db.set_cursor("account-2", "state-b")

        assert db.get_cursor("account-1") == "state-a"
        assert db.get_cursor("account-2") == "state-b"


def test_reopening_an_existing_db_file_preserves_data(tmp_path: Path) -> None:
    """Data written by one StateDB instance is visible to a fresh
    instance opened against the same file — the whole point of this
    being persistent, on-disk state rather than in-memory."""
    db_path = tmp_path / "state.sqlite3"
    with StateDB(db_path) as db:
        db.set_cursor("account-1", "state-1")
        db.mark_processed("msg-1", thread_id="thread-1", processed_at="2026-08-11T00:00:00Z")

    with StateDB(db_path) as reopened:
        assert reopened.get_cursor("account-1") == "state-1"
        assert reopened.has_processed("msg-1") is True


def test_using_the_db_after_close_raises(tmp_path: Path) -> None:
    """Calling a method after close()/context-exit fails clearly rather
    than silently operating on a dead connection."""
    db = StateDB(tmp_path / "state.sqlite3")
    db.close()

    with pytest.raises(Exception):  # noqa: B017 - sqlite3 raises ProgrammingError here
        db.get_cursor("account-1")
