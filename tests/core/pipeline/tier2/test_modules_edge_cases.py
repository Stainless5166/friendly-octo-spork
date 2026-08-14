"""Failure/edge-case tests for the concrete Tier 2 pipeline modules.

Companion to test_modules.py's acceptance tests — covers each
module's MissingMetaError, raised when it's run before the module it
depends on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.llm.base import LLMResult, Verdict, VerdictRequest
from spork.core.models import NormalizedMessage
from spork.core.pipeline.core import Payload
from spork.core.pipeline.meta import MissingMetaError
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2.meta import Tier2Meta
from spork.core.pipeline.tier2.modules import (
    ApplyVerdictActionFilter,
    BudgetGateSelector,
    CallLLMAugment,
    ConfidenceBandSelector,
    CreateDraftIfWantedFilter,
    MarkProcessedFilter,
    RecordAlertOnlyFilter,
    RecordBudgetExhaustedFilter,
    RecordLLMUsageFilter,
    ValidateVerdictFilter,
    WriteAuditEntryFilter,
)
from spork.core.rules.schema import Action
from spork.core.state.db import StateDB


class _RecordingApplier:
    def apply(self, message: NormalizedMessage, action: Action) -> None:
        pass


class _FakeAlerter:
    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        pass


class _RecordingDraftCreator:
    def create_draft(self, in_reply_to: NormalizedMessage, body: str) -> None:
        pass


class _StubLLMClient:
    def get_verdict(self, request: VerdictRequest) -> LLMResult:  # pragma: no cover - never called
        raise NotImplementedError


def _verdict() -> Verdict:
    return Verdict.model_validate(
        {
            "category": "needs_reply",
            "urgency": "high",
            "confidence": 0.9,
            "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
            "summary": "s",
            "reasoning": "r",
        }
    )


def _payload(make_message, **meta_overrides: object) -> Payload[Tier2Meta]:
    defaults: dict[str, object] = {
        "message": make_message(message_id="msg-1"),
        "to_addresses": ("me@example.com",),
        "thread_prior_subject": None,
        "thread_user_has_replied": False,
        "available_mailboxes": ("Inbox", "Needs-Reply"),
    }
    defaults.update(meta_overrides)
    return Payload(text="Body.", meta=Tier2Meta(**defaults))  # type: ignore[arg-type]


def test_budget_gate_selector_raises_when_ts_is_missing(tmp_path: Path, make_message) -> None:
    """No TimestampFilter has run yet — meta.ts is still None."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(MissingMetaError):
            BudgetGateSelector(db, daily_call_budget=10).select(_payload(make_message))


def test_call_llm_augment_raises_when_request_is_missing(make_message) -> None:
    """No BuildVerdictRequestFilter has run — meta.request is still None."""
    with pytest.raises(MissingMetaError):
        CallLLMAugment(_StubLLMClient()).augment(_payload(make_message))


def test_record_llm_usage_filter_raises_when_ts_is_missing(tmp_path: Path, make_message) -> None:
    """No TimestampFilter has run — meta.ts is still None."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(MissingMetaError):
            RecordLLMUsageFilter(db).apply(_payload(make_message))


def test_record_llm_usage_filter_raises_when_call_usage_is_missing(
    tmp_path: Path, make_message
) -> None:
    """A timestamp alone cannot invent token counts for a call result."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(MissingMetaError, match="meta.llm_usage"):
            RecordLLMUsageFilter(db).apply(_payload(make_message, ts="2026-08-14T10:00:00+00:00"))


def test_validate_verdict_filter_raises_when_verdict_is_missing(make_message) -> None:
    """No CallLLMAugment has run — meta.verdict is still None."""
    with pytest.raises(MissingMetaError):
        ValidateVerdictFilter(allowed_categories=["needs_reply"]).apply(_payload(make_message))


def test_confidence_band_selector_raises_when_verdict_is_missing(make_message) -> None:
    """No CallLLMAugment has run — meta.verdict is still None."""
    with pytest.raises(MissingMetaError):
        ConfidenceBandSelector(alert_threshold=0.55, autoact_threshold=0.85).select(
            _payload(make_message)
        )


def test_apply_verdict_action_filter_raises_when_verdict_is_missing(make_message) -> None:
    """No CallLLMAugment has run — meta.verdict is still None."""
    executor = ActionExecutor(_RecordingApplier())

    with pytest.raises(MissingMetaError):
        ApplyVerdictActionFilter(executor, PipelineObserver(_FakeAlerter())).apply(
            _payload(make_message)
        )


def test_apply_verdict_action_filter_raises_when_correlation_id_is_missing_and_alerting(
    make_message,
) -> None:
    """band=autoact_alert (about to alert), but no CorrelationIdFilter
    has run — meta.correlation_id is still None."""
    executor = ActionExecutor(_RecordingApplier())
    payload = _payload(make_message, verdict=_verdict(), band="autoact_alert")

    with pytest.raises(MissingMetaError):
        ApplyVerdictActionFilter(executor, PipelineObserver(_FakeAlerter())).apply(payload)


def test_record_alert_only_filter_raises_when_verdict_is_missing(make_message) -> None:
    """No CallLLMAugment has run — meta.verdict is still None."""
    with pytest.raises(MissingMetaError):
        RecordAlertOnlyFilter(PipelineObserver(_FakeAlerter())).apply(_payload(make_message))


def test_record_alert_only_filter_raises_when_correlation_id_is_missing(make_message) -> None:
    """No CorrelationIdFilter has run — meta.correlation_id is still
    None, and this filter always alerts."""
    payload = _payload(make_message, verdict=_verdict(), band="alert_only")

    with pytest.raises(MissingMetaError):
        RecordAlertOnlyFilter(PipelineObserver(_FakeAlerter())).apply(payload)


def test_record_budget_exhausted_filter_raises_when_correlation_id_is_missing(
    make_message,
) -> None:
    """No CorrelationIdFilter has run — meta.correlation_id is still
    None, and this filter always alerts."""
    with pytest.raises(MissingMetaError):
        RecordBudgetExhaustedFilter(PipelineObserver(_FakeAlerter())).apply(_payload(make_message))


def test_create_draft_if_wanted_filter_raises_when_verdict_is_missing(make_message) -> None:
    """No CallLLMAugment has run — meta.verdict is still None."""
    with pytest.raises(MissingMetaError):
        CreateDraftIfWantedFilter(_RecordingDraftCreator()).apply(_payload(make_message))


def test_write_audit_entry_filter_raises_when_ts_is_missing(tmp_path: Path, make_message) -> None:
    """No TimestampFilter has run yet — meta.ts is still None."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(MissingMetaError):
            WriteAuditEntryFilter(db).apply(
                _payload(make_message, audit_event="tier2_action_applied")
            )


def test_write_audit_entry_filter_raises_when_audit_event_is_missing(
    tmp_path: Path, make_message
) -> None:
    """No outcome-recording filter has run — meta.audit_event is still None."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(MissingMetaError):
            WriteAuditEntryFilter(db).apply(_payload(make_message, ts="t1"))


def test_mark_processed_filter_raises_when_ts_is_missing(tmp_path: Path, make_message) -> None:
    """No TimestampFilter has run — meta.ts is still None, even though
    meta.verdict is present."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(MissingMetaError):
            MarkProcessedFilter(db).apply(_payload(make_message, verdict=_verdict()))
