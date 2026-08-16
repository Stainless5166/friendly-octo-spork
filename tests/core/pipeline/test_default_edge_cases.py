"""Failure/edge-case tests for process_message().

Companion to test_pipeline.py's acceptance tests.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.classify.base import ClassificationResult
from spork.core.models import NormalizedMessage
from spork.core.pipeline import build_default_pipeline, process_message
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
    ts = datetime.fromisoformat(entries[0].ts)  # raises ValueError if not parseable
    # Not just parseable — genuinely UTC, per _utc_now_iso's own name and
    # docstring, not local/naive time.
    assert ts.tzinfo is not None
    assert ts.utcoffset() == timedelta(0)


def test_process_message_with_force_on_a_never_processed_message_behaves_normally(
    tmp_path: Path, make_message
) -> None:
    """force=True doesn't change behavior for the ordinary case — a
    message that was never processed to begin with is evaluated and
    acted on exactly as it would be without force, not double-applied
    or treated specially."""
    message = make_message(message_id="msg-1")
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="tag", mailbox="X"))]

    class _RecordingApplier:
        def __init__(self) -> None:
            self.calls: list[tuple[NormalizedMessage, Action]] = []

        def apply(self, message: NormalizedMessage, action: Action) -> None:
            self.calls.append((message, action))

    applier = _RecordingApplier()
    with StateDB(tmp_path / "state.sqlite3") as db:
        verdict = process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            force=True,
        )

        assert db.has_processed("msg-1") is True

    assert verdict is not None
    assert applier.calls == [(message, Action(type="tag", mailbox="X"))]


def test_process_message_uses_the_injected_correlation_id_generator(
    tmp_path: Path, make_message, caplog: pytest.LogCaptureFixture
) -> None:
    """The new_correlation_id= callable passed to process_message() must
    actually reach CorrelationIdFilter — not the default random-uuid
    generator — since a caller injecting one (e.g. a test, or a future
    cross-tier-stitching caller, §12.2) needs it to actually take
    effect, not silently be ignored in favor of the real one."""
    caplog.set_level(logging.INFO)
    message = make_message(message_id="msg-1")
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="ignore"))]

    class _NoopApplier:
        def apply(self, message: NormalizedMessage, action: Action) -> None:
            pass

    with StateDB(tmp_path / "state.sqlite3") as db:
        process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(_NoopApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
            new_correlation_id=lambda: "fixed-correlation-id",
        )

    correlation_ids = {getattr(record, "correlation_id", None) for record in caplog.records}
    assert "fixed-correlation-id" in correlation_ids


def test_process_message_uses_the_injected_classifier(tmp_path: Path, make_message) -> None:
    """The classifier= passed to process_message() must actually reach
    the rule engine — a classifier-backed condition needs it to
    evaluate at all, and a silently-dropped classifier would either
    raise (no classifier configured) or never match, either way not
    the "matched via classifier" outcome this test demands."""

    class _FixedClassifier:
        def classify(self, message: NormalizedMessage) -> ClassificationResult:
            return ClassificationResult(category="newsletter")

    message = make_message(message_id="msg-1")
    rules = [
        Rule(
            id="classifier-rule",
            when=Condition(local_classifier_category_in=["newsletter"]),
            action=Action(type="tag", mailbox="Reading"),
        )
    ]
    applier_calls: list[tuple[NormalizedMessage, Action]] = []

    class _RecordingApplier:
        def apply(self, message: NormalizedMessage, action: Action) -> None:
            applier_calls.append((message, action))

    with StateDB(tmp_path / "state.sqlite3") as db:
        verdict = process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(_RecordingApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            classifier=_FixedClassifier(),
        )

    assert verdict is not None
    assert verdict.matched_rule_id == "classifier-rule"
    assert applier_calls == [(message, Action(type="tag", mailbox="Reading"))]


def test_build_default_pipeline_defaults_to_not_forcing(tmp_path: Path, make_message) -> None:
    """Calling build_default_pipeline() without force= (its own default,
    not process_message()'s — every process_message() call passes
    force= explicitly, so this default is otherwise never exercised)
    must still include the idempotency gate: an already-processed
    message is skipped, not silently re-evaluated."""
    from spork.core.pipeline.core import Payload
    from spork.core.pipeline.meta import MessageMeta

    message = make_message(message_id="msg-1")
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="ignore"))]

    class _NoopApplier:
        def apply(self, message: NormalizedMessage, action: Action) -> None:
            pass

    with StateDB(tmp_path / "state.sqlite3") as db:
        db.mark_processed(message.message_id, thread_id=message.thread_id, processed_at="t0")
        pipeline = build_default_pipeline(
            executor=ActionExecutor(_NoopApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
        )
        result = pipeline.run(
            Payload(
                text="",
                meta=MessageMeta(
                    message=message, rules=rules, default_unmatched_action=Action(type="escalate")
                ),
            )
        )

    # Never routed through RuleEvaluationSelector at all — meta.verdict
    # stays unset, same signal process_message() itself uses for "skipped".
    assert result.meta.verdict is None
