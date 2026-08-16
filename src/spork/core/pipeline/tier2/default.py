"""build_tier2_pipeline() + process_tier2_message(): the Tier 2 pipeline, composed (§10.7).

Composes every piece §10.1-§10.6 built — the same relationship
`spork.core.pipeline.default` has to Tier 1's seven modules.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from spork.core.actions.executor import ActionExecutor
from spork.core.llm.base import LLMClient, Verdict
from spork.core.models import NormalizedMessage
from spork.core.pipeline.core import Payload, Pipeline
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2.meta import Tier2Meta
from spork.core.pipeline.tier2.modules import (
    ApplyVerdictActionFilter,
    BudgetGateSelector,
    BuildVerdictRequestFilter,
    CallLLMAugment,
    ConfidenceBandSelector,
    CorrelationIdFilter,
    CreateDraftIfWantedFilter,
    MarkProcessedFilter,
    RecordAlertOnlyFilter,
    RecordBudgetExhaustedFilter,
    RecordLLMUsageFilter,
    TimestampFilter,
    ValidateVerdictFilter,
    WriteAuditEntryFilter,
)
from spork.core.pipeline.tracing import wrap_selector, wrap_stages
from spork.core.providers.base import DraftCreator
from spork.core.state.db import StateDB


def _utc_now_iso() -> str:
    """Default clock: an ISO 8601 UTC timestamp string."""
    return datetime.now(UTC).isoformat()


def _new_correlation_id() -> str:
    """Default id generator: a random hex correlation id (§12.2)."""
    return uuid.uuid4().hex


def build_tier2_pipeline(
    *,
    llm_client: LLMClient,
    executor: ActionExecutor,
    draft_creator: DraftCreator,
    state_db: StateDB,
    ops: PipelineObserver,
    allowed_categories: Sequence[str],
    daily_call_budget: int,
    alert_threshold: float,
    autoact_threshold: float,
    max_body_chars: int = 4000,
    now: Callable[[], str] = _utc_now_iso,
    new_correlation_id: Callable[[], str] = _new_correlation_id,
) -> Pipeline[Tier2Meta]:
    """Compose the modules that make up the Tier 2 pipeline.

    `"autoact"` and `"autoact_alert"` deliberately route to the same
    `act` Pipeline object — the only difference between the two bands
    is whether a human gets alerted (§12.2's `ApplyVerdictActionFilter`
    wiring), not a difference in what this pipeline does.
    """
    act: Pipeline[Tier2Meta] = Pipeline(
        wrap_stages(
            [
                ApplyVerdictActionFilter(executor, ops),
                CreateDraftIfWantedFilter(draft_creator),
                WriteAuditEntryFilter(state_db),
                MarkProcessedFilter(state_db),
            ],
            ops,
        )
    )
    alert_only: Pipeline[Tier2Meta] = Pipeline(
        wrap_stages(
            [
                RecordAlertOnlyFilter(ops),
                CreateDraftIfWantedFilter(draft_creator),
                WriteAuditEntryFilter(state_db),
                MarkProcessedFilter(state_db),
            ],
            ops,
        )
    )
    budget_ok: Pipeline[Tier2Meta] = Pipeline(
        wrap_stages(
            [
                BuildVerdictRequestFilter(allowed_categories, max_body_chars),
                CallLLMAugment(llm_client),
                RecordLLMUsageFilter(state_db),
                ValidateVerdictFilter(allowed_categories),
            ],
            ops,
        ),
        selector=wrap_selector(ConfidenceBandSelector(alert_threshold, autoact_threshold), ops),
        routes={"autoact": act, "autoact_alert": act, "alert_only": alert_only},
    )
    budget_exhausted: Pipeline[Tier2Meta] = Pipeline(
        wrap_stages(
            [
                RecordBudgetExhaustedFilter(ops),
                WriteAuditEntryFilter(state_db),
                MarkProcessedFilter(state_db),
            ],
            ops,
        )
    )
    return Pipeline(
        wrap_stages([TimestampFilter(now), CorrelationIdFilter(new_correlation_id)], ops),
        selector=wrap_selector(BudgetGateSelector(state_db, daily_call_budget), ops),
        routes={"budget_ok": budget_ok, "budget_exhausted": budget_exhausted},
    )


def process_tier2_message(
    message: NormalizedMessage,
    *,
    to_addresses: Sequence[str],
    thread_prior_subject: str | None,
    thread_user_has_replied: bool,
    available_mailboxes: Sequence[str],
    llm_client: LLMClient,
    executor: ActionExecutor,
    draft_creator: DraftCreator,
    state_db: StateDB,
    ops: PipelineObserver,
    allowed_categories: Sequence[str],
    daily_call_budget: int,
    alert_threshold: float,
    autoact_threshold: float,
    max_body_chars: int = 4000,
    now: Callable[[], str] = _utc_now_iso,
    new_correlation_id: Callable[[], str] = _new_correlation_id,
) -> Verdict | None:
    """Run one escalated message through the full Tier 2 pipeline.

    Returns `None` when the daily call budget is already exhausted —
    that return value doubles as "no verdict was produced," the same
    way `process_message()`'s `None` doubles as "wasn't acted on."

    Deciding *which* escalated message to call this on isn't this
    function's job (docs/DESIGN.md §10.7). Tier 1 leaves an escalation
    pending, and this pipeline owns the terminal processed mark after its
    action, alert-only, or budget-exhausted outcome succeeds.
    """
    pipeline = build_tier2_pipeline(
        llm_client=llm_client,
        executor=executor,
        draft_creator=draft_creator,
        state_db=state_db,
        ops=ops,
        allowed_categories=allowed_categories,
        daily_call_budget=daily_call_budget,
        alert_threshold=alert_threshold,
        autoact_threshold=autoact_threshold,
        max_body_chars=max_body_chars,
        now=now,
        new_correlation_id=new_correlation_id,
    )
    payload: Payload[Tier2Meta] = Payload(
        text=message.body_text,
        meta=Tier2Meta(
            message=message,
            to_addresses=to_addresses,
            thread_prior_subject=thread_prior_subject,
            thread_user_has_replied=thread_user_has_replied,
            available_mailboxes=available_mailboxes,
        ),
    )
    result = pipeline.run(payload)
    return result.meta.verdict
