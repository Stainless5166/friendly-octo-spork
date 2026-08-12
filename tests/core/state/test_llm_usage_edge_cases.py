"""Failure/edge-case tests for StateDB's llm_usage table.

Companion to test_llm_usage.py's acceptance tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.state.db import LLMUsage, StateDB


def test_record_llm_call_with_zero_tokens_still_increments_calls(tmp_path: Path) -> None:
    """A call with no token cost reported (e.g. a cached/free response)
    is still a call — calls increments even when both token counts
    are 0."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.record_llm_call("2026-08-12", tokens_in=0, tokens_out=0)

        assert db.get_llm_usage("2026-08-12") == LLMUsage(
            date="2026-08-12", calls=1, tokens_in=0, tokens_out=0
        )


def test_llm_usage_persists_across_reopening_the_database(tmp_path: Path) -> None:
    """Usage recorded before a close is still there after reopening
    the same file — the same durability contract StateDB gives
    push_cursor/processed_messages, extended to llm_usage."""
    db_path = tmp_path / "state.sqlite3"
    with StateDB(db_path) as db:
        db.record_llm_call("2026-08-12", tokens_in=500, tokens_out=120)

    with StateDB(db_path) as db:
        assert db.get_llm_usage("2026-08-12") == LLMUsage(
            date="2026-08-12", calls=1, tokens_in=500, tokens_out=120
        )


def test_record_llm_call_rejects_negative_tokens_in(tmp_path: Path) -> None:
    """BUG FOUND WHILE TESTING: an unguarded record_llm_call() would
    happily accumulate a negative tokens_in into the running total —
    a caller bug (e.g. computing a token delta wrong) would silently
    corrupt a day's usage total in a way that's hard to notice later,
    since SQLite has no opinion on the sign of an INTEGER column.
    Fixed by rejecting negative values eagerly, same "fail loud rather
    than store garbage" instinct as everywhere else in spork.core."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(ValueError, match="tokens_in"):
            db.record_llm_call("2026-08-12", tokens_in=-1, tokens_out=0)


def test_record_llm_call_rejects_negative_tokens_out(tmp_path: Path) -> None:
    """Same guard, the other token count."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(ValueError, match="tokens_out"):
            db.record_llm_call("2026-08-12", tokens_in=0, tokens_out=-1)
