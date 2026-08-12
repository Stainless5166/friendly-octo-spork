"""Acceptance tests for the concrete message-pipeline modules (§9.4).

Each module's tests construct a bare Payload[MessageMeta] and assert
what .apply()/.select() returns — no Pipeline, no other module, no
full process_message() call needed. That's the whole point of
splitting process_message() into named modules.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.actions.executor import ActionExecutor
from spork.core.models import NormalizedMessage
from spork.core.pipeline.core import Payload
from spork.core.pipeline.meta import MessageMeta
from spork.core.pipeline.modules import (
    ApplyActionFilter,
    IdempotencyGateSelector,
    MarkProcessedFilter,
    RecordEscalationFilter,
    RuleEvaluationSelector,
    TimestampFilter,
    WriteAuditEntryFilter,
)
from spork.core.rules.schema import Action, Condition, Rule
from spork.core.state.db import StateDB


class _RecordingApplier:
    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, Action]] = []

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self.calls.append((message, action))


def _payload(make_message, **meta_overrides: object) -> Payload[MessageMeta]:
    defaults: dict[str, object] = {
        "message": make_message(message_id="msg-1"),
        "rules": [],
        "default_unmatched_action": Action(type="escalate"),
    }
    defaults.update(meta_overrides)
    return Payload(text="", meta=MessageMeta(**defaults))  # type: ignore[arg-type]


def test_idempotency_gate_selector_routes_skip_for_an_already_processed_message(
    tmp_path: Path, make_message
) -> None:
    """A message already marked processed routes to "skip"."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.mark_processed("msg-1", thread_id="thread-1", processed_at="t0")
        branch, _ = IdempotencyGateSelector(db).select(_payload(make_message))

    assert branch == "skip"


def test_idempotency_gate_selector_routes_continue_for_a_new_message(
    tmp_path: Path, make_message
) -> None:
    """A message never seen before routes to "continue"."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        branch, _ = IdempotencyGateSelector(db).select(_payload(make_message))

    assert branch == "continue"


def test_timestamp_filter_sets_ts_from_the_injected_clock(make_message) -> None:
    """The filter calls the given clock and stores its result in meta.ts."""
    result = TimestampFilter(now=lambda: "fixed-ts").apply(_payload(make_message))

    assert result.meta.ts == "fixed-ts"


def test_rule_evaluation_selector_routes_terminal_for_a_matched_rule(make_message) -> None:
    """A message matching a terminal rule gets that verdict and routes
    to "terminal"."""
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="ignore"))]
    branch, result = RuleEvaluationSelector().select(_payload(make_message, rules=rules))

    assert branch == "terminal"
    assert result.meta.verdict is not None
    assert result.meta.verdict.matched_rule_id == "r1"


def test_rule_evaluation_selector_routes_escalate_when_nothing_matches(make_message) -> None:
    """No matching rule falls through to the default policy — here,
    escalate — and routes to "escalate"."""
    branch, result = RuleEvaluationSelector().select(_payload(make_message, rules=[]))

    assert branch == "escalate"
    assert result.meta.verdict is not None
    assert result.meta.verdict.action.type == "escalate"


def test_apply_action_filter_calls_the_executor_and_sets_audit_fields(make_message) -> None:
    """A terminal verdict's action is applied via the executor, and the
    audit fields the next stage needs are set."""
    applier = _RecordingApplier()
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="ignore"))]
    _, terminal_payload = RuleEvaluationSelector().select(_payload(make_message, rules=rules))

    result = ApplyActionFilter(ActionExecutor(applier)).apply(terminal_payload)

    assert result.meta.audit_event == "action_applied"
    assert result.meta.audit_detail_json == '{"action_type": "ignore"}'


def test_record_escalation_filter_sets_the_escalation_audit_event(make_message) -> None:
    """The escalate branch's counterpart to ApplyActionFilter — no
    action applied, just the audit event recorded."""
    branch_payload = RuleEvaluationSelector().select(_payload(make_message, rules=[]))[1]

    result = RecordEscalationFilter().apply(branch_payload)

    assert result.meta.audit_event == "escalated_pending_tier2"


def test_write_audit_entry_filter_writes_what_meta_describes(tmp_path: Path, make_message) -> None:
    """Whatever meta.audit_event/audit_detail_json say gets written —
    generic across both branches."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        payload = _payload(
            make_message, ts="t1", audit_event="action_applied", audit_detail_json='{"x": 1}'
        )
        WriteAuditEntryFilter(db).apply(payload)

        entries = db.get_audit_entries(jmap_id="msg-1")

    assert len(entries) == 1
    assert entries[0].event == "action_applied"
    assert entries[0].detail_json == '{"x": 1}'


def test_mark_processed_filter_writes_the_processed_row(tmp_path: Path, make_message) -> None:
    """The message is recorded as processed with the verdict's action
    and the shared timestamp."""
    verdict = RuleEvaluationSelector().select(_payload(make_message, rules=[]))[1].meta.verdict

    with StateDB(tmp_path / "state.sqlite3") as db:
        payload = _payload(make_message, verdict=verdict, ts="t1")
        MarkProcessedFilter(db).apply(payload)

        assert db.has_processed("msg-1") is True
