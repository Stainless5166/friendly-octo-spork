"""process_message(): idempotency + rule evaluation + action + audit (§9).

The one call a real message actually goes through — everything else
in `spork.core` (the rule engine, the action executor, the state DB)
is a piece this function composes, not a piece that composes itself.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from spork.core.actions.executor import ActionExecutor
from spork.core.classify.base import TextClassifier
from spork.core.models import NormalizedMessage
from spork.core.rules.engine import RuleVerdict, evaluate
from spork.core.rules.schema import Action, Rule
from spork.core.state.db import StateDB


def _utc_now_iso() -> str:
    """Default clock: an ISO 8601 UTC timestamp string."""
    return datetime.now(UTC).isoformat()


def process_message(
    message: NormalizedMessage,
    rules: Sequence[Rule],
    *,
    default_unmatched_action: Action,
    executor: ActionExecutor,
    state_db: StateDB,
    classifier: TextClassifier | None = None,
    now: Callable[[], str] = _utc_now_iso,
) -> RuleVerdict | None:
    """Run one message through the full Tier 1 pipeline.

    Returns `None` without evaluating anything if `message` was
    already processed (docs/DESIGN.md §11's idempotency guarantee) —
    that return value doubles as "was this actually acted on just
    now." A message is only marked processed *after* its action
    successfully applies: if `executor.execute()` raises, nothing is
    recorded, so the next poll/push cycle picks the same message back
    up instead of silently losing it.

    An `escalate` verdict is handled per the interim policy in
    docs/DESIGN.md §9: never passed to `executor` (which would reject
    it), recorded, and marked processed anyway so the daemon doesn't
    re-evaluate the same message forever while Tier 2 (M3) remains
    unbuilt.
    """
    if state_db.has_processed(message.message_id):
        return None

    verdict = evaluate(
        message,
        rules,
        default_unmatched_action=default_unmatched_action,
        classifier=classifier,
    )

    ts = now()
    if verdict.action.type == "escalate":
        state_db.write_audit_entry(
            ts=ts,
            jmap_id=message.message_id,
            event="escalated_pending_tier2",
        )
    else:
        executor.execute(message, verdict.action)
        state_db.write_audit_entry(
            ts=ts,
            jmap_id=message.message_id,
            event="action_applied",
            detail_json=f'{{"action_type": "{verdict.action.type}"}}',
        )

    state_db.mark_processed(
        message.message_id,
        thread_id=message.thread_id,
        processed_at=ts,
        tier_reached="tier1",
        action_taken=verdict.action.type,
    )
    return verdict
