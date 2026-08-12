"""The concrete Filters/Selectors that reproduce M2's process_message() (§9.4).

Eight small modules, each independently constructible and testable
against a bare `Payload[MessageMeta]` — see docs/DESIGN.md §9.4 for
why. `spork.core.pipeline.default.build_default_pipeline()` wires them
together.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from spork.core.actions.executor import ActionExecutor
from spork.core.pipeline.core import Payload
from spork.core.pipeline.meta import MessageMeta, MissingMetaError
from spork.core.pipeline.observer import PipelineObserver
from spork.core.rules.engine import evaluate
from spork.core.state.db import StateDB


class IdempotencyGateSelector:
    """Routes "skip" for an already-processed message, "continue" otherwise."""

    def __init__(self, state_db: StateDB) -> None:
        self._state_db = state_db

    def select(self, payload: Payload[MessageMeta]) -> tuple[str, Payload[MessageMeta]]:
        if self._state_db.has_processed(payload.meta.message.message_id):
            return "skip", payload
        return "continue", payload


class TimestampFilter:
    """Calls the clock exactly once; every later module reads meta.ts.

    Closes a real M2 gap: the old `process_message()` called `now()`
    twice (once for the audit entry, once for `processed_at`), which
    could record two microseconds-apart timestamps for one event.
    """

    def __init__(self, now: Callable[[], str]) -> None:
        self._now = now

    def apply(self, payload: Payload[MessageMeta]) -> Payload[MessageMeta]:
        return dataclasses.replace(payload, meta=dataclasses.replace(payload.meta, ts=self._now()))


class CorrelationIdFilter:
    """Calls the injected id generator exactly once; every later module
    (and PipelineObserver.trace()/alert()) reads meta.correlation_id.

    Mirrors TimestampFilter's now: Callable DI exactly, one call per
    pipeline run (docs/DESIGN.md §12.2) — a fresh id per run, not per
    message's full cross-tier lifetime (see §12.2's stated limitation).
    """

    def __init__(self, new_id: Callable[[], str]) -> None:
        self._new_id = new_id

    def apply(self, payload: Payload[MessageMeta]) -> Payload[MessageMeta]:
        return dataclasses.replace(
            payload, meta=dataclasses.replace(payload.meta, correlation_id=self._new_id())
        )


class RuleEvaluationSelector:
    """Runs the Tier 1 rule engine; routes "terminal" or "escalate"."""

    def select(self, payload: Payload[MessageMeta]) -> tuple[str, Payload[MessageMeta]]:
        meta = payload.meta
        verdict = evaluate(
            meta.message,
            meta.rules,
            default_unmatched_action=meta.default_unmatched_action,
            classifier=meta.classifier,
        )
        updated = dataclasses.replace(payload, meta=dataclasses.replace(meta, verdict=verdict))
        branch = "escalate" if verdict.action.type == "escalate" else "terminal"
        return branch, updated


class ApplyActionFilter:
    """Applies a terminal verdict's action via the injected ActionExecutor.

    Sets meta.audit_event/audit_detail_json describing what happened,
    generically, for WriteAuditEntryFilter to log — this filter
    doesn't write the audit log itself.
    """

    def __init__(self, executor: ActionExecutor) -> None:
        self._executor = executor

    def apply(self, payload: Payload[MessageMeta]) -> Payload[MessageMeta]:
        verdict = payload.meta.verdict
        if verdict is None:
            raise MissingMetaError(
                "ApplyActionFilter requires meta.verdict — run RuleEvaluationSelector first"
            )
        self._executor.execute(payload.meta.message, verdict.action)
        detail_json = f'{{"action_type": "{verdict.action.type}"}}'
        return dataclasses.replace(
            payload,
            meta=dataclasses.replace(
                payload.meta, audit_event="action_applied", audit_detail_json=detail_json
            ),
        )


class RecordEscalationFilter:
    """The "escalate" branch's counterpart to ApplyActionFilter.

    No action to apply — escalation means Tier 2 hasn't produced a
    terminal action yet (docs/DESIGN.md §9's interim policy) — just
    records that the message was escalated for the next filter to log.
    Also fires an immediate alert when the matched rule's action opted
    in (`Action.alert_immediately`, §12.2) — a VIP-sender rule, e.g. —
    rather than the generic "wait for Tier 2" treatment every other
    escalation gets.
    """

    def __init__(self, ops: PipelineObserver) -> None:
        self._ops = ops

    def apply(self, payload: Payload[MessageMeta]) -> Payload[MessageMeta]:
        meta = payload.meta
        if meta.verdict is None:
            raise MissingMetaError(
                "RecordEscalationFilter requires meta.verdict — run RuleEvaluationSelector first"
            )
        if meta.verdict.action.alert_immediately:
            if meta.correlation_id is None:
                raise MissingMetaError(
                    "RecordEscalationFilter requires meta.correlation_id to alert — "
                    "run CorrelationIdFilter first"
                )
            reason = meta.verdict.action.reason or meta.verdict.matched_rule_id or "escalated"
            self._ops.alert(
                meta.correlation_id,
                f"Escalated: {reason}",
                f"{meta.message.from_address}: {meta.message.subject}",
            )
        return dataclasses.replace(
            payload,
            meta=dataclasses.replace(meta, audit_event="escalated_pending_tier2"),
        )


class WriteAuditEntryFilter:
    """Writes whatever meta.audit_event/audit_detail_json describe.

    Generic across both the terminal and escalate branches — it
    doesn't know or care which module set those fields, only that one
    did.
    """

    def __init__(self, state_db: StateDB) -> None:
        self._state_db = state_db

    def apply(self, payload: Payload[MessageMeta]) -> Payload[MessageMeta]:
        meta = payload.meta
        if meta.ts is None or meta.audit_event is None:
            raise MissingMetaError(
                "WriteAuditEntryFilter requires meta.ts and meta.audit_event — "
                "run TimestampFilter and a verdict-handling filter first"
            )
        self._state_db.write_audit_entry(
            ts=meta.ts,
            jmap_id=meta.message.message_id,
            event=meta.audit_event,
            detail_json=meta.audit_detail_json,
        )
        return payload


class MarkProcessedFilter:
    """Records the message as processed — the idempotency write side."""

    def __init__(self, state_db: StateDB) -> None:
        self._state_db = state_db

    def apply(self, payload: Payload[MessageMeta]) -> Payload[MessageMeta]:
        meta = payload.meta
        if meta.verdict is None or meta.ts is None:
            raise MissingMetaError(
                "MarkProcessedFilter requires meta.verdict and meta.ts — "
                "run RuleEvaluationSelector and TimestampFilter first"
            )
        self._state_db.mark_processed(
            meta.message.message_id,
            thread_id=meta.message.thread_id,
            processed_at=meta.ts,
            tier_reached="tier1",
            action_taken=meta.verdict.action.type,
        )
        return payload
