"""The concrete Filters/Selectors/Augment that make up the Tier 2 pipeline (§10.7).

Thirteen small modules, each independently constructible and testable
against a bare `Payload[Tier2Meta]` — same rationale as
`spork.core.pipeline.modules`. `spork.core.pipeline.tier2.default.build_tier2_pipeline()`
wires them together.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence

from spork.core.actions.executor import ActionExecutor
from spork.core.llm.base import LLMClient, VerdictRequest
from spork.core.llm.budget import has_budget_remaining
from spork.core.llm.clean import clean_body
from spork.core.llm.confidence import confidence_band
from spork.core.llm.validate import validate_verdict
from spork.core.pipeline.core import Payload
from spork.core.pipeline.meta import MissingMetaError
from spork.core.pipeline.tier2.meta import Tier2Meta
from spork.core.providers.base import DraftCreator
from spork.core.state.db import StateDB


class TimestampFilter:
    """Calls the clock exactly once; every later module reads meta.ts."""

    def __init__(self, now: Callable[[], str]) -> None:
        self._now = now

    def apply(self, payload: Payload[Tier2Meta]) -> Payload[Tier2Meta]:
        return dataclasses.replace(payload, meta=dataclasses.replace(payload.meta, ts=self._now()))


class BudgetGateSelector:
    """Routes "budget_exhausted" once today's Tier 2 call count reaches
    `daily_call_budget`, "budget_ok" otherwise (§10.4)."""

    def __init__(self, state_db: StateDB, daily_call_budget: int) -> None:
        self._state_db = state_db
        self._daily_call_budget = daily_call_budget

    def select(self, payload: Payload[Tier2Meta]) -> tuple[str, Payload[Tier2Meta]]:
        ts = payload.meta.ts
        if ts is None:
            raise MissingMetaError(
                "BudgetGateSelector requires meta.ts — run TimestampFilter first"
            )
        usage = self._state_db.get_llm_usage(ts[:10])
        if has_budget_remaining(usage, daily_call_budget=self._daily_call_budget):
            return "budget_ok", payload
        return "budget_exhausted", payload


class BuildVerdictRequestFilter:
    """Cleans payload.text via clean_body() and assembles a
    VerdictRequest from it plus meta's caller-supplied fields."""

    def __init__(self, max_body_chars: int = 4000) -> None:
        self._max_body_chars = max_body_chars

    def apply(self, payload: Payload[Tier2Meta]) -> Payload[Tier2Meta]:
        meta = payload.meta
        cleaned = clean_body(payload.text, max_chars=self._max_body_chars)
        request = VerdictRequest(
            subject=meta.message.subject,
            from_address=meta.message.from_address,
            to_addresses=tuple(meta.to_addresses),
            cleaned_body=cleaned,
            thread_prior_subject=meta.thread_prior_subject,
            thread_user_has_replied=meta.thread_user_has_replied,
            available_mailboxes=tuple(meta.available_mailboxes),
        )
        return dataclasses.replace(
            payload, text=cleaned, meta=dataclasses.replace(meta, request=request)
        )


class CallLLMAugment:
    """The one Augment in this pipeline — the only stage that reaches
    outside the payload. Calls `llm_client.get_verdict()`, the seam
    the external Anthropic API sits behind (§10.7): swap in a real
    client once it's ready, nothing else here changes.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def augment(self, payload: Payload[Tier2Meta]) -> Payload[Tier2Meta]:
        request = payload.meta.request
        if request is None:
            raise MissingMetaError(
                "CallLLMAugment requires meta.request — run BuildVerdictRequestFilter first"
            )
        verdict = self._llm_client.get_verdict(request)
        return dataclasses.replace(payload, meta=dataclasses.replace(payload.meta, verdict=verdict))


class RecordLLMUsageFilter:
    """Records that a Tier 2 call was made, immediately after it
    happens — the call cost budget regardless of whether the response
    later fails validation (§10.4, §10.7).

    Known limitation: recorded with tokens_in=tokens_out=0.
    `LLMClient.get_verdict()` returns a `Verdict`, not a token-usage
    figure, so real counts aren't available until a live client
    reports them — call-count enforcement doesn't need them, but
    `spork status`'s token-spend display will read zeros until then.
    """

    def __init__(self, state_db: StateDB) -> None:
        self._state_db = state_db

    def apply(self, payload: Payload[Tier2Meta]) -> Payload[Tier2Meta]:
        ts = payload.meta.ts
        if ts is None:
            raise MissingMetaError(
                "RecordLLMUsageFilter requires meta.ts — run TimestampFilter first"
            )
        self._state_db.record_llm_call(ts[:10], tokens_in=0, tokens_out=0)
        return payload


class ValidateVerdictFilter:
    """Validates meta.verdict against the configured category set and
    meta.available_mailboxes (§10.2) — raises on failure."""

    def __init__(self, allowed_categories: Sequence[str]) -> None:
        self._allowed_categories = allowed_categories

    def apply(self, payload: Payload[Tier2Meta]) -> Payload[Tier2Meta]:
        meta = payload.meta
        if meta.verdict is None:
            raise MissingMetaError(
                "ValidateVerdictFilter requires meta.verdict — run CallLLMAugment first"
            )
        validated = validate_verdict(
            meta.verdict,
            allowed_categories=self._allowed_categories,
            allowed_mailboxes=meta.available_mailboxes,
        )
        return dataclasses.replace(payload, meta=dataclasses.replace(meta, verdict=validated))


class ConfidenceBandSelector:
    """Classifies meta.verdict.confidence into one of §11's three bands
    (§10.3), sets meta.band, and routes accordingly."""

    def __init__(self, alert_threshold: float, autoact_threshold: float) -> None:
        self._alert_threshold = alert_threshold
        self._autoact_threshold = autoact_threshold

    def select(self, payload: Payload[Tier2Meta]) -> tuple[str, Payload[Tier2Meta]]:
        verdict = payload.meta.verdict
        if verdict is None:
            raise MissingMetaError(
                "ConfidenceBandSelector requires meta.verdict — run CallLLMAugment first"
            )
        band = confidence_band(
            verdict.confidence,
            alert_threshold=self._alert_threshold,
            autoact_threshold=self._autoact_threshold,
        )
        updated = dataclasses.replace(payload, meta=dataclasses.replace(payload.meta, band=band))
        return band, updated


class ApplyVerdictActionFilter:
    """Applies verdict.suggested_action via the injected ActionExecutor
    (the same one Tier 1 terminal actions use) — the "autoact" and
    "autoact_alert" branches' shared filter (§10.7)."""

    def __init__(self, executor: ActionExecutor) -> None:
        self._executor = executor

    def apply(self, payload: Payload[Tier2Meta]) -> Payload[Tier2Meta]:
        meta = payload.meta
        if meta.verdict is None:
            raise MissingMetaError(
                "ApplyVerdictActionFilter requires meta.verdict — run CallLLMAugment first"
            )
        self._executor.execute(meta.message, meta.verdict.suggested_action)
        detail_json = (
            f'{{"action_type": "{meta.verdict.suggested_action.type}", '
            f'"category": "{meta.verdict.category}", "band": "{meta.band}"}}'
        )
        return dataclasses.replace(
            payload,
            meta=dataclasses.replace(
                meta, audit_event="tier2_action_applied", audit_detail_json=detail_json
            ),
        )


class RecordAlertOnlyFilter:
    """The "alert_only" branch's counterpart to ApplyVerdictActionFilter
    — no action applied, just records why (§10.7)."""

    def apply(self, payload: Payload[Tier2Meta]) -> Payload[Tier2Meta]:
        meta = payload.meta
        if meta.verdict is None:
            raise MissingMetaError(
                "RecordAlertOnlyFilter requires meta.verdict — run CallLLMAugment first"
            )
        detail_json = f'{{"category": "{meta.verdict.category}", "band": "{meta.band}"}}'
        return dataclasses.replace(
            payload,
            meta=dataclasses.replace(
                meta, audit_event="tier2_alert_only_no_action", audit_detail_json=detail_json
            ),
        )


class RecordBudgetExhaustedFilter:
    """The "budget_exhausted" branch's counterpart — Tier 2 was skipped
    entirely, matching §10's cost-control policy: escalated mail that
    can't get a Tier 2 call goes straight to Needs-Review + alert
    rather than being silently dropped."""

    def apply(self, payload: Payload[Tier2Meta]) -> Payload[Tier2Meta]:
        return dataclasses.replace(
            payload,
            meta=dataclasses.replace(payload.meta, audit_event="tier2_budget_exhausted"),
        )


class CreateDraftIfWantedFilter:
    """Creates a draft via DraftCreator (§10.6) if meta.verdict.draft_reply
    is set — a no-op otherwise. Runs on every non-budget-exhausted
    branch: a draft is never sent, so there's no reason to withhold
    one from a message a human still has to review."""

    def __init__(self, draft_creator: DraftCreator) -> None:
        self._draft_creator = draft_creator

    def apply(self, payload: Payload[Tier2Meta]) -> Payload[Tier2Meta]:
        meta = payload.meta
        if meta.verdict is None:
            raise MissingMetaError(
                "CreateDraftIfWantedFilter requires meta.verdict — run CallLLMAugment first"
            )
        if meta.verdict.draft_reply is not None:
            self._draft_creator.create_draft(meta.message, meta.verdict.draft_reply)
        return payload


class WriteAuditEntryFilter:
    """Writes whatever meta.audit_event/audit_detail_json describe —
    generic across all four outcome branches, mirrors Tier 1's."""

    def __init__(self, state_db: StateDB) -> None:
        self._state_db = state_db

    def apply(self, payload: Payload[Tier2Meta]) -> Payload[Tier2Meta]:
        meta = payload.meta
        if meta.ts is None or meta.audit_event is None:
            raise MissingMetaError(
                "WriteAuditEntryFilter requires meta.ts and meta.audit_event — "
                "run TimestampFilter and an outcome-recording filter first"
            )
        self._state_db.write_audit_entry(
            ts=meta.ts,
            jmap_id=meta.message.message_id,
            event=meta.audit_event,
            detail_json=meta.audit_detail_json,
        )
        return payload


class MarkProcessedFilter:
    """Records the message as processed with tier_reached="tier2".

    Unlike Tier 1's, doesn't require meta.verdict — the
    "budget_exhausted" branch never sets one. Overwrites Tier 1's row
    for the same message (StateDB.mark_processed()'s existing upsert,
    built for `spork reclassify`) rather than erroring — correct here
    too, since a Tier 2 run's outcome supersedes Tier 1's "escalated"
    placeholder (§10.7).
    """

    def __init__(self, state_db: StateDB) -> None:
        self._state_db = state_db

    def apply(self, payload: Payload[Tier2Meta]) -> Payload[Tier2Meta]:
        meta = payload.meta
        if meta.ts is None:
            raise MissingMetaError(
                "MarkProcessedFilter requires meta.ts — run TimestampFilter first"
            )
        action_taken = meta.verdict.suggested_action.type if meta.verdict is not None else None
        self._state_db.mark_processed(
            meta.message.message_id,
            thread_id=meta.message.thread_id,
            processed_at=meta.ts,
            tier_reached="tier2",
            verdict_json=meta.verdict.model_dump_json() if meta.verdict is not None else None,
            action_taken=action_taken,
        )
        return payload
