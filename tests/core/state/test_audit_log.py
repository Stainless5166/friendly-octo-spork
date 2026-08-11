"""Acceptance tests for StateDB's audit_log table (docs/DESIGN.md §7.4).

Milestone (docs/ROADMAP.md M2, item 2 of 5 — extends the existing
StateDB, no blockers). Uses a real SQLite file under pytest's
tmp_path, same as test_db.py.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.state.db import StateDB


def test_write_audit_entry_then_get_audit_entries_returns_it(tmp_path: Path) -> None:
    """A written entry is returned by get_audit_entries() with the same
    fields — the basic record/read-back round trip."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.write_audit_entry(
            ts="2026-08-11T00:00:00Z",
            jmap_id="msg-1",
            event="action_applied",
            detail_json='{"action": "move"}',
        )

        entries = db.get_audit_entries()

        assert len(entries) == 1
        assert entries[0].jmap_id == "msg-1"
        assert entries[0].event == "action_applied"
        assert entries[0].detail_json == '{"action": "move"}'


def test_get_audit_entries_filters_by_jmap_id(tmp_path: Path) -> None:
    """Passing jmap_id= only returns that message's entries — the shape
    `spork logs --message-id <id>` (M5) will need."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.write_audit_entry(ts="2026-08-11T00:00:00Z", jmap_id="msg-1", event="e1")
        db.write_audit_entry(ts="2026-08-11T00:01:00Z", jmap_id="msg-2", event="e2")

        entries = db.get_audit_entries(jmap_id="msg-1")

        assert [e.jmap_id for e in entries] == ["msg-1"]


def test_get_audit_entries_returns_oldest_first(tmp_path: Path) -> None:
    """Multiple entries come back in the order they were written — a
    reviewable timeline, not an arbitrary order."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.write_audit_entry(ts="2026-08-11T00:00:00Z", jmap_id="msg-1", event="first")
        db.write_audit_entry(ts="2026-08-11T00:01:00Z", jmap_id="msg-1", event="second")

        entries = db.get_audit_entries(jmap_id="msg-1")

        assert [e.event for e in entries] == ["first", "second"]


def test_get_audit_entries_returns_empty_list_when_none_written(tmp_path: Path) -> None:
    """A fresh state DB has no audit entries — an empty list, not an
    error."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        assert db.get_audit_entries() == []
