"""Failure/edge-case tests for process_message().

Companion to test_pipeline.py's acceptance tests.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.models import NormalizedMessage
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.rules.schema import Action, Condition, Rule
from spork.core.state.db import StateDB


class _FailingApplier:
    def apply(self, message: NormalizedMessage, action: Action) -> None:
        raise RuntimeError("simulated backend failure")


class _FakeAlerter:
    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        pass


def test_process_message_propagates_executor_failure_and_does_not_mark_processed(
    tmp_path: Path, make_message
) -> None:
    """If the executor fails (a real backend mutation rejected), the
    exception propagates and the message is NOT marked processed —
    the whole point of ordering mark_processed after the action apply
    is that a failed action gets retried on the next cycle, not lost."""
    message = make_message(message_id="msg-1")
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="move", mailbox="X"))]

    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(RuntimeError):
            process_message(
                message,
                rules,
                default_unmatched_action=Action(type="escalate"),
                executor=ActionExecutor(_FailingApplier()),
                state_db=db,
                ops=PipelineObserver(_FakeAlerter()),
                now=lambda: "t1",
            )

        assert db.has_processed("msg-1") is False
        assert db.get_audit_entries(jmap_id="msg-1") == []


def test_mark_processed_uses_the_injected_clock(tmp_path: Path, make_message) -> None:
    """processed_at (not just the audit entry's ts) reflects the
    injected clock, not a real wall-clock call."""
    db_path = tmp_path / "state.sqlite3"
    message = make_message(message_id="msg-1")
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="ignore"))]

    class _NoopApplier:
        def apply(self, message: NormalizedMessage, action: Action) -> None:
            pass

    with StateDB(db_path) as db:
        process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(_NoopApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "fixed-timestamp",
        )

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT processed_at FROM processed_messages WHERE jmap_id = ?", ("msg-1",)
    ).fetchone()
    conn.close()

    assert row == ("fixed-timestamp",)


def test_default_clock_produces_a_real_parseable_timestamp(tmp_path: Path, make_message) -> None:
    """Omitting now= (the real, non-injected path) still produces a
    genuine, parseable timestamp — proving the default clock itself
    works, not just that a fake one can be substituted for it."""
    message = make_message(message_id="msg-1")
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="ignore"))]

    class _NoopApplier:
        def apply(self, message: NormalizedMessage, action: Action) -> None:
            pass

    with StateDB(tmp_path / "state.sqlite3") as db:
        verdict = process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(_NoopApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
        )

        entries = db.get_audit_entries(jmap_id="msg-1")

    assert verdict is not None
    datetime.fromisoformat(entries[0].ts)  # raises ValueError if not parseable
