"""build_default_pipeline() + process_message(): the M2 pipeline, composed (§9.4).

The one call a real message actually goes through — everything else
in `spork.core.pipeline` (the generic framework, `MessageMeta`, the
eight concrete modules) is a piece this file composes, not a piece
that composes itself.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from spork.core.actions.executor import ActionExecutor
from spork.core.classify.base import TextClassifier
from spork.core.models import NormalizedMessage
from spork.core.pipeline.core import Payload, Pipeline
from spork.core.pipeline.meta import MessageMeta
from spork.core.pipeline.modules import (
    ApplyActionFilter,
    CorrelationIdFilter,
    IdempotencyGateSelector,
    MarkProcessedFilter,
    RecordEscalationFilter,
    RuleEvaluationSelector,
    TimestampFilter,
    WriteAuditEntryFilter,
)
from spork.core.pipeline.observer import PipelineObserver
from spork.core.rules.engine import RuleVerdict
from spork.core.rules.schema import Action, Rule
from spork.core.state.db import StateDB


def _utc_now_iso() -> str:
    """Default clock: an ISO 8601 UTC timestamp string."""
    return datetime.now(UTC).isoformat()


def _new_correlation_id() -> str:
    """Default id generator: a random hex correlation id (§12.2)."""
    return uuid.uuid4().hex


def build_default_pipeline(
    *,
    executor: ActionExecutor,
    state_db: StateDB,
    ops: PipelineObserver,
    now: Callable[[], str] = _utc_now_iso,
    new_correlation_id: Callable[[], str] = _new_correlation_id,
) -> Pipeline[MessageMeta]:
    """Compose the modules that reproduce M2's process_message() behavior.

    Named and reusable on its own — the exact seam M3's Tier 2
    escalation work slots into: the "escalate" route is a
    `Pipeline[MessageMeta]` like any other route, so pointing it at a
    pipeline that calls Claude first is a change to *what that route
    points at*, never a rewrite of `Pipeline`, `RuleEvaluationSelector`,
    or the "terminal" route.
    """
    terminal: Pipeline[MessageMeta] = Pipeline(
        [
            ApplyActionFilter(executor),
            WriteAuditEntryFilter(state_db),
            MarkProcessedFilter(state_db),
        ]
    )
    escalate: Pipeline[MessageMeta] = Pipeline(
        [
            RecordEscalationFilter(ops),
            WriteAuditEntryFilter(state_db),
            MarkProcessedFilter(state_db),
        ]
    )
    process = Pipeline(
        [TimestampFilter(now), CorrelationIdFilter(new_correlation_id)],
        selector=RuleEvaluationSelector(),
        routes={"terminal": terminal, "escalate": escalate},
    )
    return Pipeline(
        selector=IdempotencyGateSelector(state_db),
        routes={"skip": Pipeline(), "continue": process},
    )


def process_message(
    message: NormalizedMessage,
    rules: Sequence[Rule],
    *,
    default_unmatched_action: Action,
    executor: ActionExecutor,
    state_db: StateDB,
    ops: PipelineObserver,
    classifier: TextClassifier | None = None,
    now: Callable[[], str] = _utc_now_iso,
    new_correlation_id: Callable[[], str] = _new_correlation_id,
) -> RuleVerdict | None:
    """Run one message through the full Tier 1 pipeline.

    Returns `None` without evaluating anything if `message` was
    already processed (docs/DESIGN.md §11's idempotency guarantee) —
    that return value doubles as "was this actually acted on just
    now." A message is only marked processed *after* its action
    successfully applies: if a module raises, nothing is recorded, so
    the next poll/push cycle picks the same message back up instead of
    silently losing it.

    An `escalate` verdict is handled per the interim policy in
    docs/DESIGN.md §9: never passed to the action executor (which
    would reject it), recorded, and marked processed anyway so the
    daemon doesn't re-evaluate the same message forever while Tier 2
    (M3) remains unbuilt.
    """
    pipeline = build_default_pipeline(
        executor=executor,
        state_db=state_db,
        ops=ops,
        now=now,
        new_correlation_id=new_correlation_id,
    )
    payload: Payload[MessageMeta] = Payload(
        text="",
        meta=MessageMeta(
            message=message,
            rules=rules,
            default_unmatched_action=default_unmatched_action,
            classifier=classifier,
        ),
    )
    result = pipeline.run(payload)
    return result.meta.verdict
