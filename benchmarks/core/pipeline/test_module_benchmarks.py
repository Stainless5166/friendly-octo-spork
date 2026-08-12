"""Per-module performance benchmarks for spork.core.pipeline (docs/DESIGN.md §9.4).

Deliberately outside `tests/` (pytest's `testpaths`) — see
benchmarks/README.md. Each module's benchmark constructs the same kind
of bare Payload the correctness tests in tests/core/pipeline/ use,
proving the "no Pipeline, no other module needed" independence claim
applies to performance measurement too, not just correctness.
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
from spork.core.rules.engine import RuleVerdict
from spork.core.rules.schema import Action, Condition, Rule
from spork.core.state.db import StateDB


class _NoopApplier:
    def apply(self, message: NormalizedMessage, action: Action) -> None:
        pass


def _message() -> NormalizedMessage:
    return NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address="a@example.com",
        from_domain="example.com",
        subject="Benchmark",
        body_text="Benchmark body.",
    )


def _payload(**overrides: object) -> Payload[MessageMeta]:
    defaults: dict[str, object] = {
        "message": _message(),
        "rules": [],
        "default_unmatched_action": Action(type="escalate"),
    }
    defaults.update(overrides)
    return Payload(text="", meta=MessageMeta(**defaults))  # type: ignore[arg-type]


def test_idempotency_gate_selector_benchmark(tmp_path: Path, benchmark) -> None:
    with StateDB(tmp_path / "state.sqlite3") as db:
        selector = IdempotencyGateSelector(db)
        benchmark(selector.select, _payload())


def test_timestamp_filter_benchmark(benchmark) -> None:
    filt = TimestampFilter(now=lambda: "fixed-ts")
    benchmark(filt.apply, _payload())


def test_rule_evaluation_selector_benchmark_first_rule_matches(benchmark) -> None:
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="ignore"))]
    benchmark(RuleEvaluationSelector().select, _payload(rules=rules))


def test_rule_evaluation_selector_benchmark_200_non_matching_rules(benchmark) -> None:
    rules = [
        Rule(
            id=f"r{i}",
            when=Condition(from_domain_in=[f"other{i}.example.com"]),
            action=Action(type="ignore"),
        )
        for i in range(200)
    ]
    benchmark(RuleEvaluationSelector().select, _payload(rules=rules))


def test_apply_action_filter_benchmark(benchmark) -> None:
    executor = ActionExecutor(_NoopApplier())
    verdict = RuleVerdict(action=Action(type="ignore"), matched_rule_id=None)
    benchmark(ApplyActionFilter(executor).apply, _payload(verdict=verdict))


def test_record_escalation_filter_benchmark(benchmark) -> None:
    benchmark(RecordEscalationFilter().apply, _payload())


def test_write_audit_entry_filter_benchmark(tmp_path: Path, benchmark) -> None:
    with StateDB(tmp_path / "state.sqlite3") as db:
        payload = _payload(ts="t1", audit_event="action_applied")
        benchmark(WriteAuditEntryFilter(db).apply, payload)


def test_mark_processed_filter_benchmark(tmp_path: Path, benchmark) -> None:
    with StateDB(tmp_path / "state.sqlite3") as db:
        verdict = RuleVerdict(action=Action(type="ignore"), matched_rule_id=None)
        payload = _payload(verdict=verdict, ts="t1")
        benchmark(MarkProcessedFilter(db).apply, payload)
