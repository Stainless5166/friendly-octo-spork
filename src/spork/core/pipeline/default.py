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
from spork.core.pipeline.tracing import wrap_selector, wrap_stages
from spork.core.receipts.pipeline import ArchiveReceiptAugment, ReceiptArchiveComponents
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
    force: bool = False,
    receipt_archive: ReceiptArchiveComponents | None = None,
) -> Pipeline[MessageMeta]:
    """Compose the modules that reproduce M2's process_message() behavior.

    Named and reusable on its own — the exact seam M3's Tier 2
    escalation work slots into: the "escalate" route is a
    `Pipeline[MessageMeta]` like any other route, so pointing it at a
    pipeline that calls Claude first is a change to *what that route
    points at*, never a rewrite of `Pipeline`, `RuleEvaluationSelector`,
    or the "terminal" route.

    `force=True` (M5, for `spork reclassify <id>`, docs/DESIGN.md §9.4)
    omits `IdempotencyGateSelector` from the composed pipeline entirely
    — `process` runs directly, so `has_processed()` is never even
    called, rather than being consulted and then overridden. This
    keeps the gate's own logic single-purpose (it only ever means
    "already processed," never "already processed, unless told not to
    care") and avoids adding a bypass branch it would otherwise need to
    know about.

    `receipt_archive` (§9.5, M10) wires the `"archive_receipt"` route
    when given; omitting it (the default — every existing caller) means
    a rule matching `archive_receipt` reaches `RuleEvaluationSelector`
    with nowhere to route to, so `Pipeline.run()` raises
    `UnknownBranchError` — a real config error at composition time, not
    a silent no-op, same "fail loud on a real gap" stance the rest of
    this codebase takes.
    """
    terminal: Pipeline[MessageMeta] = Pipeline(
        wrap_stages(
            [
                ApplyActionFilter(executor),
                WriteAuditEntryFilter(state_db),
                MarkProcessedFilter(state_db),
            ],
            ops,
        )
    )
    escalate: Pipeline[MessageMeta] = Pipeline(
        wrap_stages(
            [
                RecordEscalationFilter(ops),
                WriteAuditEntryFilter(state_db),
            ],
            ops,
        )
    )
    routes: dict[str, Pipeline[MessageMeta]] = {"terminal": terminal, "escalate": escalate}
    if receipt_archive is not None:
        routes["archive_receipt"] = Pipeline(
            wrap_stages(
                [
                    ArchiveReceiptAugment(state_db, receipt_archive),
                    WriteAuditEntryFilter(state_db),
                    MarkProcessedFilter(state_db),
                ],
                ops,
            )
        )
    process = Pipeline(
        wrap_stages([TimestampFilter(now), CorrelationIdFilter(new_correlation_id)], ops),
        selector=wrap_selector(RuleEvaluationSelector(), ops),
        routes=routes,
    )
    if force:
        return process
    return Pipeline(
        selector=wrap_selector(IdempotencyGateSelector(state_db), ops),
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
    force: bool = False,
    receipt_archive: ReceiptArchiveComponents | None = None,
) -> RuleVerdict | None:
    """Run one message through the full Tier 1 pipeline.

    Returns `None` without evaluating anything if `message` was
    already processed (docs/DESIGN.md §11's idempotency guarantee) —
    that return value doubles as "was this actually acted on just
    now." A message is only marked processed *after* its action
    successfully applies: if a module raises, nothing is recorded, so
    the next poll/push cycle picks the same message back up instead of
    silently losing it. `force=True` (M5, for `spork reclassify <id>`)
    skips that idempotency check entirely — see
    `build_default_pipeline()`'s docstring for why.

    An `escalate` verdict is recorded as pending Tier 2 and deliberately
    remains unprocessed. Tier 2 owns the terminal processed mark, so an
    LLM/provider failure leaves the message retryable after restart.

    `receipt_archive` (§9.5, M10) is passed straight through to
    `build_default_pipeline()` — see its docstring for what omitting it
    means for an `archive_receipt` rule.
    """
    pipeline = build_default_pipeline(
        executor=executor,
        state_db=state_db,
        ops=ops,
        now=now,
        new_correlation_id=new_correlation_id,
        force=force,
        receipt_archive=receipt_archive,
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
