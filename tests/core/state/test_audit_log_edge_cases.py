"""Failure/edge-case tests for the audit_log table.

Companion to test_audit_log.py's acceptance tests.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.state.db import StateDB


def test_get_audit_entries_for_unknown_jmap_id_returns_empty(tmp_path: Path) -> None:
    """Filtering to a jmap_id with no entries returns [], not an error —
    distinct from an entirely empty audit log (test_audit_log.py)."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.write_audit_entry(ts="2026-08-11T00:00:00Z", jmap_id="msg-1", event="e1")

        assert db.get_audit_entries(jmap_id="msg-does-not-exist") == []


def test_audit_log_persists_across_reopening_the_db_file(tmp_path: Path) -> None:
    """Entries written by one StateDB instance are visible to a fresh
    instance opened against the same file — genuine on-disk
    persistence, matching processed_messages/push_cursor's behavior."""
    db_path = tmp_path / "state.sqlite3"
    with StateDB(db_path) as db:
        db.write_audit_entry(ts="2026-08-11T00:00:00Z", jmap_id="msg-1", event="e1")

    with StateDB(db_path) as reopened:
        entries = reopened.get_audit_entries(jmap_id="msg-1")

    assert [e.event for e in entries] == ["e1"]
