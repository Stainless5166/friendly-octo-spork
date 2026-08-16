"""Acceptance tests for the concrete Tier 2 pipeline modules (§10.7).

Each module's tests construct a bare Payload[Tier2Meta] and assert
what .apply()/.select()/.augment() returns — no Pipeline, no other
module, no full process_tier2_message() call needed. Same rationale
as tests/core/pipeline/test_modules.py for the Tier 1 modules.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.actions.executor import ActionExecutor
from spork.core.llm.base import LLMCallUsage, LLMResult, Verdict, VerdictRequest
from spork.core.models import NormalizedMessage
from spork.core.pipeline.core import Payload
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
from spork.core.rules.schema import Action
from spork.core.state.db import StateDB


class _FakeAlerter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify(self, title, body, *, url=None, urgency="normal") -> None:  # type: ignore[no-untyped-def]
        self.calls.append({"title": title, "body": body, "url": url, "urgency": urgency})


class _RecordingApplier:
    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, Action]] = []

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self.calls.append((message, action))


class _RecordingDraftCreator:
    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, str]] = []

    def create_draft(self, in_reply_to: NormalizedMessage, body: str) -> None:
        self.calls.append((in_reply_to, body))


class _StubLLMClient:
    """Returns a fixed Verdict regardless of the request — proves
    CallLLMAugment genuinely delegates to whatever LLMClient it's
    given, without needing a live one."""

    def __init__(self, verdict: Verdict) -> None:
        self._verdict = verdict
        self.requests: list[VerdictRequest] = []

    def get_verdict(self, request: VerdictRequest) -> LLMResult:
        self.requests.append(request)
        return LLMResult(
            verdict=self._verdict,
            usage=LLMCallUsage(tokens_in=17, tokens_out=9),
        )


def _verdict(**overrides: object) -> Verdict:
    payload: dict[str, object] = {
        "category": "needs_reply",
        "urgency": "high",
        "confidence": 0.9,
        "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
        "summary": "s",
        "reasoning": "r",
    }
    payload.update(overrides)
    return Verdict.model_validate(payload)


def _payload(make_message, **meta_overrides: object) -> Payload[Tier2Meta]:
    defaults: dict[str, object] = {
        "message": make_message(message_id="msg-1"),
        "to_addresses": ("me@example.com",),
        "thread_prior_subject": None,
        "thread_user_has_replied": False,
        "available_mailboxes": ("Inbox", "Needs-Reply"),
    }
    defaults.update(meta_overrides)
    return Payload(text=defaults.pop("text", "Body text."), meta=Tier2Meta(**defaults))  # type: ignore[arg-type]


def test_timestamp_filter_sets_ts_from_the_injected_clock(make_message) -> None:
    result = TimestampFilter(now=lambda: "fixed-ts").apply(_payload(make_message))

    assert result.meta.ts == "fixed-ts"


def test_correlation_id_filter_sets_correlation_id_from_the_injected_generator(
    make_message,
) -> None:
    """Mirrors TimestampFilter's now: Callable DI — same pattern,
    Tier 2's own module (never shares concrete modules with Tier 1)."""
    result = CorrelationIdFilter(new_id=lambda: "fixed-corr-id").apply(_payload(make_message))

    assert result.meta.correlation_id == "fixed-corr-id"


def test_budget_gate_selector_routes_budget_ok_when_under_the_limit(
    tmp_path: Path, make_message
) -> None:
    """Fewer calls today than the budget: routes "budget_ok"."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        branch, _ = BudgetGateSelector(db, daily_call_budget=10).select(
            _payload(make_message, ts="2026-08-12T00:00:00Z")
        )

    assert branch == "budget_ok"


def test_budget_gate_selector_routes_budget_exhausted_at_the_limit(
    tmp_path: Path, make_message
) -> None:
    """Calls already at the budget for today: routes "budget_exhausted"."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.record_llm_call("2026-08-12", tokens_in=0, tokens_out=0)
        branch, _ = BudgetGateSelector(db, daily_call_budget=1).select(
            _payload(make_message, ts="2026-08-12T00:00:00Z")
        )

    assert branch == "budget_exhausted"


def test_build_verdict_request_filter_cleans_the_body_and_builds_the_request(
    make_message,
) -> None:
    """payload.text is cleaned via clean_body(); meta.request is built
    from the cleaned text plus meta's caller-supplied fields."""
    payload = _payload(
        make_message,
        text="<p>Hello there.</p>",
        thread_prior_subject="Original subject",
        thread_user_has_replied=True,
    )

    result = BuildVerdictRequestFilter(available_categories=["needs_reply", "fyi"]).apply(payload)

    assert result.text == "Hello there."
    assert result.meta.request is not None
    assert result.meta.request.cleaned_body == "Hello there."
    assert result.meta.request.subject == payload.meta.message.subject
    assert result.meta.request.thread_prior_subject == "Original subject"
    assert result.meta.request.thread_user_has_replied is True
    assert result.meta.request.available_mailboxes == ("Inbox", "Needs-Reply")
    assert result.meta.request.available_categories == ("needs_reply", "fyi")


def test_call_llm_augment_delegates_to_the_client_and_sets_the_verdict(make_message) -> None:
    """The Augment calls llm_client.get_verdict(meta.request) and
    stores the result in meta.verdict — the one I/O stage."""
    verdict = _verdict()
    client = _StubLLMClient(verdict)
    payload = BuildVerdictRequestFilter(available_categories=["needs_reply"]).apply(
        _payload(make_message)
    )

    result = CallLLMAugment(client).augment(payload)

    assert result.meta.verdict == verdict
    assert client.requests == [payload.meta.request]


def test_record_llm_usage_filter_records_one_call(tmp_path: Path, make_message) -> None:
    """A call is recorded against meta.ts's date."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        payload = _payload(
            make_message,
            ts="2026-08-12T10:00:00Z",
            llm_usage=LLMCallUsage(tokens_in=17, tokens_out=9),
        )
        RecordLLMUsageFilter(db).apply(payload)

        usage = db.get_llm_usage("2026-08-12")

    assert usage.calls == 1
    assert usage.tokens_in == 17
    assert usage.tokens_out == 9


def test_validate_verdict_filter_passes_through_a_valid_verdict(make_message) -> None:
    """A verdict whose category/mailbox are both configured passes
    through unchanged."""
    payload = _payload(make_message, verdict=_verdict(category="needs_reply"))

    result = ValidateVerdictFilter(allowed_categories=["needs_reply"]).apply(payload)

    assert result.meta.verdict == payload.meta.verdict


def test_confidence_band_selector_routes_autoact_for_high_confidence(make_message) -> None:
    payload = _payload(make_message, verdict=_verdict(confidence=0.95))

    branch, result = ConfidenceBandSelector(alert_threshold=0.55, autoact_threshold=0.85).select(
        payload
    )

    assert branch == "autoact"
    assert result.meta.band == "autoact"


def test_confidence_band_selector_routes_alert_only_for_low_confidence(make_message) -> None:
    payload = _payload(make_message, verdict=_verdict(confidence=0.2))

    branch, result = ConfidenceBandSelector(alert_threshold=0.55, autoact_threshold=0.85).select(
        payload
    )

    assert branch == "alert_only"
    assert result.meta.band == "alert_only"


def test_apply_verdict_action_filter_calls_the_executor_and_sets_audit_fields(
    make_message,
) -> None:
    applier = _RecordingApplier()
    verdict = _verdict(suggested_action={"type": "tag", "mailbox": "Needs-Reply"}, urgency="medium")
    payload = _payload(make_message, verdict=verdict, band="autoact", correlation_id="corr-1")

    result = ApplyVerdictActionFilter(
        ActionExecutor(applier), PipelineObserver(_FakeAlerter())
    ).apply(payload)

    assert applier.calls == [(payload.meta.message, verdict.suggested_action)]
    assert result.meta.audit_event is not None
    assert "autoact" in result.meta.audit_detail_json


def test_apply_verdict_action_filter_does_not_alert_for_plain_autoact(make_message) -> None:
    """A vanilla "autoact" outcome with non-high urgency: silent, per
    the band's whole purpose (act without bothering a human)."""
    alerter = _FakeAlerter()
    verdict = _verdict(urgency="medium")
    payload = _payload(make_message, verdict=verdict, band="autoact", correlation_id="corr-1")

    ApplyVerdictActionFilter(ActionExecutor(_RecordingApplier()), PipelineObserver(alerter)).apply(
        payload
    )

    assert alerter.calls == []


def test_apply_verdict_action_filter_alerts_for_autoact_alert_band(make_message) -> None:
    """ "autoact_alert" alerts even though it's the same shared act
    Pipeline as plain "autoact" (docs/DESIGN.md §10.7) — meta.band is
    what distinguishes the two, not a different filter."""
    alerter = _FakeAlerter()
    verdict = _verdict(urgency="medium")
    payload = _payload(make_message, verdict=verdict, band="autoact_alert", correlation_id="corr-1")

    ApplyVerdictActionFilter(ActionExecutor(_RecordingApplier()), PipelineObserver(alerter)).apply(
        payload
    )

    assert len(alerter.calls) == 1


def test_apply_verdict_action_filter_alerts_for_high_urgency_even_in_plain_autoact(
    make_message,
) -> None:
    """The orthogonal dimension from §12's intro: urgency=="high" alerts
    regardless of band, including inside plain "autoact"."""
    alerter = _FakeAlerter()
    verdict = _verdict(urgency="high")
    payload = _payload(make_message, verdict=verdict, band="autoact", correlation_id="corr-1")

    ApplyVerdictActionFilter(ActionExecutor(_RecordingApplier()), PipelineObserver(alerter)).apply(
        payload
    )

    assert len(alerter.calls) == 1
    assert alerter.calls[0]["urgency"] == "critical"


def test_record_alert_only_filter_sets_the_audit_event(make_message) -> None:
    payload = _payload(make_message, verdict=_verdict(), band="alert_only", correlation_id="corr-1")

    result = RecordAlertOnlyFilter(PipelineObserver(_FakeAlerter())).apply(payload)

    assert result.meta.audit_event is not None


def test_record_alert_only_filter_always_alerts(make_message) -> None:
    """The alert_only band's entire purpose is "a human must decide" —
    it alerts unconditionally, unlike the other three trigger points."""
    alerter = _FakeAlerter()
    payload = _payload(
        make_message, verdict=_verdict(urgency="low"), band="alert_only", correlation_id="corr-1"
    )

    RecordAlertOnlyFilter(PipelineObserver(alerter)).apply(payload)

    assert len(alerter.calls) == 1
    assert alerter.calls[0]["urgency"] == "low"


def test_record_budget_exhausted_filter_sets_the_audit_event(make_message) -> None:
    payload = _payload(make_message, correlation_id="corr-1")

    result = RecordBudgetExhaustedFilter(PipelineObserver(_FakeAlerter())).apply(payload)

    assert result.meta.audit_event is not None


def test_record_budget_exhausted_filter_always_alerts_at_critical_urgency(make_message) -> None:
    """§10's documented policy: budget-exhausted mail goes straight to
    Needs-Review + alert, never silently dropped."""
    alerter = _FakeAlerter()
    payload = _payload(make_message, correlation_id="corr-1")

    RecordBudgetExhaustedFilter(PipelineObserver(alerter)).apply(payload)

    assert len(alerter.calls) == 1
    assert alerter.calls[0]["urgency"] == "critical"


def test_create_draft_if_wanted_filter_creates_a_draft_when_one_is_present(make_message) -> None:
    draft_creator = _RecordingDraftCreator()
    verdict = _verdict(draft_reply="Friday 2pm works for me.")
    payload = _payload(make_message, verdict=verdict)

    CreateDraftIfWantedFilter(draft_creator).apply(payload)

    assert draft_creator.calls == [(payload.meta.message, "Friday 2pm works for me.")]


def test_create_draft_if_wanted_filter_is_a_noop_when_no_draft_reply(make_message) -> None:
    draft_creator = _RecordingDraftCreator()
    payload = _payload(make_message, verdict=_verdict(draft_reply=None))

    CreateDraftIfWantedFilter(draft_creator).apply(payload)

    assert draft_creator.calls == []


def test_write_audit_entry_filter_writes_what_meta_describes(tmp_path: Path, make_message) -> None:
    with StateDB(tmp_path / "state.sqlite3") as db:
        payload = _payload(
            make_message, ts="t1", audit_event="tier2_autoact", audit_detail_json='{"x": 1}'
        )
        WriteAuditEntryFilter(db).apply(payload)

        entries = db.get_audit_entries(jmap_id="msg-1")

    assert len(entries) == 1
    assert entries[0].event == "tier2_autoact"


def test_mark_processed_filter_writes_the_processed_row_with_a_verdict(
    tmp_path: Path, make_message
) -> None:
    verdict = _verdict()
    with StateDB(tmp_path / "state.sqlite3") as db:
        payload = _payload(make_message, verdict=verdict, ts="t1")
        MarkProcessedFilter(db).apply(payload)

        assert db.has_processed("msg-1") is True


def test_mark_processed_filter_writes_the_processed_row_without_a_verdict(
    tmp_path: Path, make_message
) -> None:
    """The budget-exhausted branch never sets meta.verdict — unlike
    Tier 1's MarkProcessedFilter, this one doesn't require it."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        payload = _payload(make_message, ts="t1")
        MarkProcessedFilter(db).apply(payload)

        assert db.has_processed("msg-1") is True
