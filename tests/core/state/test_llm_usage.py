"""Acceptance tests for StateDB's llm_usage table (docs/DESIGN.md §7.4, §10.4).

Milestone (docs/ROADMAP.md M3, "daily_call_budget enforcement +
llm_usage tracking" — extends the existing StateDB, no blockers). Uses
a real SQLite file under pytest's tmp_path, same as test_db.py.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.state.db import LLMUsage, StateDB


def test_get_llm_usage_is_zeroed_for_a_date_never_recorded(tmp_path: Path) -> None:
    """A date with no recorded calls is zeros, not None — callers never
    special-case "never called today" separately from "called zero
    times today."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        usage = db.get_llm_usage("2026-08-12")

        assert usage == LLMUsage(date="2026-08-12", calls=0, tokens_in=0, tokens_out=0)


def test_record_llm_call_then_get_llm_usage_reflects_it(tmp_path: Path) -> None:
    """One recorded call is reflected in the next read."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.record_llm_call("2026-08-12", tokens_in=500, tokens_out=120)

        usage = db.get_llm_usage("2026-08-12")

        assert usage == LLMUsage(date="2026-08-12", calls=1, tokens_in=500, tokens_out=120)


def test_record_llm_call_accumulates_across_multiple_calls_same_day(tmp_path: Path) -> None:
    """Two calls on the same date sum, both calls and tokens — this is
    how a running daemon's daily spend actually grows."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.record_llm_call("2026-08-12", tokens_in=500, tokens_out=120)
        db.record_llm_call("2026-08-12", tokens_in=300, tokens_out=80)

        usage = db.get_llm_usage("2026-08-12")

        assert usage == LLMUsage(date="2026-08-12", calls=2, tokens_in=800, tokens_out=200)


def test_record_llm_call_keeps_different_dates_independent(tmp_path: Path) -> None:
    """Usage is tracked per date — one day's calls never leak into
    another's total."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.record_llm_call("2026-08-11", tokens_in=100, tokens_out=20)
        db.record_llm_call("2026-08-12", tokens_in=200, tokens_out=40)

        assert db.get_llm_usage("2026-08-11") == LLMUsage(
            date="2026-08-11", calls=1, tokens_in=100, tokens_out=20
        )
        assert db.get_llm_usage("2026-08-12") == LLMUsage(
            date="2026-08-12", calls=1, tokens_in=200, tokens_out=40
        )
