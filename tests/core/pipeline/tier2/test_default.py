"""Acceptance tests for process_tier2_message() (docs/DESIGN.md §10.7).

Uses RecordedLLMClient (§10.5) as the LLMClient — proving the whole
Tier 2 pipeline runs end to end with no live Anthropic API call
needed. Ties the budget check, the LLM call, verdict validation,
confidence gating, action execution, draft creation, and audit/
idempotency together against real (tmp_path) StateDB/RecordedLLMClient
and stub Provider-side appliers.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.context.base import ContextResult, ContextSnippet
from spork.core.context.clients.null import NullContextProvider
from spork.core.llm.base import LLMCallUsage, LLMResult, Verdict
from spork.core.llm.clients.recorded import RecordedLLMClient
from spork.core.models import NormalizedMessage
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2 import process_tier2_message
from spork.core.rules.schema import Action
from spork.core.state.db import StateDB


class _RecordingApplier:
    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, Action]] = []

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self.calls.append((message, action))


class _FakeAlerter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        self.calls.append({"title": title, "body": body, "url": url, "urgency": urgency})


class _RecordingDraftCreator:
    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, str]] = []

    def create_draft(self, in_reply_to: NormalizedMessage, body: str) -> None:
        self.calls.append((in_reply_to, body))


class _NeverCalledLLMClient:
    """An LLMClient that fails the test if it's ever actually called —
    proves the budget-exhausted branch skips CallLLMAugment entirely,
    not just discards its result."""

    def get_verdict(self, request: object) -> object:
        pytest.fail("LLMClient.get_verdict() should never be called when budget is exhausted")


def _write_responses(path: Path, **entries: object) -> None:
    path.write_text(json.dumps(entries))


def _high_confidence_response(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "category": "needs_reply",
        "urgency": "high",
        "confidence": 0.95,
        "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
        "summary": "Client wants to move Thursday's call to Friday 2pm.",
        "reasoning": "Direct scheduling question.",
    }
    payload.update(overrides)
    return payload


def _default_kwargs(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "to_addresses": ("me@example.com",),
        "thread_prior_subject": None,
        "thread_user_has_replied": False,
        "available_mailboxes": ("Inbox", "Needs-Reply"),
        "allowed_categories": ["needs_reply", "fyi"],
        "daily_call_budget": 200,
        "alert_threshold": 0.55,
        "autoact_threshold": 0.85,
        "context_provider": NullContextProvider(),
        "ops": PipelineObserver(_FakeAlerter()),
        "now": lambda: "2026-08-12T10:00:00Z",
    }
    defaults.update(overrides)
    return defaults


def test_process_tier2_message_autoacts_on_a_high_confidence_verdict(
    tmp_path: Path, make_message
) -> None:
    """A high-confidence verdict's suggested_action is applied, the
    message is marked processed as tier2, and the verdict is returned."""
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path, **{"Test subject": _high_confidence_response()})
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1", subject="Test subject")

    with StateDB(tmp_path / "state.sqlite3") as db:
        verdict = process_tier2_message(
            message,
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(applier),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            **_default_kwargs(),
        )

        assert db.has_processed("msg-1") is True

    assert verdict is not None
    assert verdict.category == "needs_reply"
    assert applier.calls == [(message, Action(type="tag", mailbox="Needs-Reply"))]


def test_process_tier2_message_traces_every_stage_it_runs(
    tmp_path: Path, make_message, caplog: pytest.LogCaptureFixture
) -> None:
    """docs/DESIGN.md §9.4/§12.2 (M7): every module build_tier2_pipeline()
    composes is wrapped with TracingStage/TracingSelector, same as
    Tier 1."""
    caplog.set_level(logging.INFO)
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path, **{"Test subject": _high_confidence_response()})
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1", subject="Test subject")

    with StateDB(tmp_path / "state.sqlite3") as db:
        process_tier2_message(
            message,
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(applier),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            **_default_kwargs(),
        )

    for stage_name in (
        "BudgetGateSelector",
        "FetchContextAugment",
        "BuildVerdictRequestFilter",
        "CallLLMAugment",
        "ValidateVerdictFilter",
        "ConfidenceBandSelector",
        "ApplyVerdictActionFilter",
        "WriteAuditEntryFilter",
        "MarkProcessedFilter",
    ):
        assert stage_name in caplog.text, f"{stage_name} never traced"


class _RecordingLLMClient:
    """Records the VerdictRequest it was called with — proves
    build_tier2_pipeline() actually threads allowed_categories into the
    prompt the model sees, not just into ValidateVerdictFilter's
    post-hoc check."""

    def __init__(self, response: dict[str, object]) -> None:
        self._verdict = Verdict.model_validate(response)
        self.requests: list[object] = []

    def get_verdict(self, request: object) -> object:
        self.requests.append(request)
        return LLMResult(verdict=self._verdict, usage=LLMCallUsage(tokens_in=1, tokens_out=1))


def test_process_tier2_message_sends_allowed_categories_to_the_model(
    tmp_path: Path, make_message
) -> None:
    """docs/ROADMAP.md M3 follow-up: the model is told the deployment's
    configured category set the same way it's already told the
    mailbox set — previously allowed_categories only reached
    ValidateVerdictFilter's post-hoc check, never the prompt itself."""
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1", subject="Test subject")
    client = _RecordingLLMClient(_high_confidence_response())

    with StateDB(tmp_path / "state.sqlite3") as db:
        process_tier2_message(
            message,
            llm_client=client,
            executor=ActionExecutor(applier),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            **_default_kwargs(),
        )

    assert len(client.requests) == 1
    assert client.requests[0].available_categories == ("needs_reply", "fyi")


class _StubContextProvider:
    """Returns a fixed ContextResult regardless of the message — same
    role _RecordingLLMClient plays above, for the context seam."""

    def __init__(self, result: ContextResult) -> None:
        self._result = result

    def get_context(self, message: object) -> ContextResult:
        return self._result


def test_process_tier2_message_sends_context_snippets_to_the_model(
    tmp_path: Path, make_message
) -> None:
    """docs/DESIGN.md §10.8 (item 3): a configured ContextProvider's
    result reaches the actual prompt, flattened into
    VerdictRequest.context_snippets — the read-only knowledgebase seam
    end to end, not just constructible in isolation."""
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1", subject="Test subject")
    client = _RecordingLLMClient(_high_confidence_response())
    context_provider = _StubContextProvider(
        ContextResult(snippets=(ContextSnippet(source="notes/a.md", text="A note."),))
    )
    kwargs = _default_kwargs()
    kwargs["context_provider"] = context_provider

    with StateDB(tmp_path / "state.sqlite3") as db:
        process_tier2_message(
            message,
            llm_client=client,
            executor=ActionExecutor(applier),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            **kwargs,
        )

    assert len(client.requests) == 1
    assert client.requests[0].context_snippets == ("notes/a.md: A note.",)


def test_process_tier2_message_sends_no_context_snippets_when_none_configured(
    tmp_path: Path, make_message
) -> None:
    """The default NullContextProvider is the real "no knowledgebase
    configured" state — an empty tuple, not a missing field or a
    crash."""
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1", subject="Test subject")
    client = _RecordingLLMClient(_high_confidence_response())

    with StateDB(tmp_path / "state.sqlite3") as db:
        process_tier2_message(
            message,
            llm_client=client,
            executor=ActionExecutor(applier),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            **_default_kwargs(),
        )

    assert client.requests[0].context_snippets == ()


def test_process_tier2_message_does_not_act_on_a_low_confidence_verdict(
    tmp_path: Path, make_message
) -> None:
    """A low-confidence verdict is alert_only — no action applied, but
    still marked processed and the verdict still returned."""
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path, **{"Test subject": _high_confidence_response(confidence=0.2)})
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1", subject="Test subject")

    with StateDB(tmp_path / "state.sqlite3") as db:
        verdict = process_tier2_message(
            message,
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(applier),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            **_default_kwargs(),
        )

        assert db.has_processed("msg-1") is True

    assert verdict is not None
    assert applier.calls == []


def test_process_tier2_message_alerts_for_a_low_confidence_verdict(
    tmp_path: Path, make_message
) -> None:
    """End to end: alert_only always alerts through the injected
    PipelineObserver (docs/DESIGN.md §12.2)."""
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path, **{"Test subject": _high_confidence_response(confidence=0.2)})
    message = make_message(message_id="msg-1", subject="Test subject")
    alerter = _FakeAlerter()

    with StateDB(tmp_path / "state.sqlite3") as db:
        process_tier2_message(
            message,
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(_RecordingApplier()),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            **_default_kwargs(ops=PipelineObserver(alerter)),
        )

    assert len(alerter.calls) == 1


def test_process_tier2_message_creates_a_draft_when_the_verdict_wants_one(
    tmp_path: Path, make_message
) -> None:
    """A verdict with draft_reply set creates a real draft via
    DraftCreator."""
    responses_path = tmp_path / "responses.json"
    _write_responses(
        responses_path,
        **{"Test subject": _high_confidence_response(draft_reply="Friday 2pm works.")},
    )
    draft_creator = _RecordingDraftCreator()
    message = make_message(message_id="msg-1", subject="Test subject")

    with StateDB(tmp_path / "state.sqlite3") as db:
        process_tier2_message(
            message,
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(_RecordingApplier()),
            draft_creator=draft_creator,
            state_db=db,
            **_default_kwargs(),
        )

    assert draft_creator.calls == [(message, "Friday 2pm works.")]


def test_process_tier2_message_returns_none_when_budget_is_exhausted(
    tmp_path: Path, make_message
) -> None:
    """A daily_call_budget already reached skips the LLM call entirely
    — no verdict, no action, but the message is still marked processed
    (§10's cost-control policy: never silently dropped)."""
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1", subject="Test subject")

    with StateDB(tmp_path / "state.sqlite3") as db:
        db.record_llm_call("2026-08-12", tokens_in=0, tokens_out=0)

        verdict = process_tier2_message(
            message,
            llm_client=_NeverCalledLLMClient(),
            executor=ActionExecutor(applier),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            **_default_kwargs(daily_call_budget=1),
        )

        assert db.has_processed("msg-1") is True

    assert verdict is None
    assert applier.calls == []


def test_process_tier2_message_writes_an_audit_entry(tmp_path: Path, make_message) -> None:
    """The run leaves a trace in the audit log, regardless of branch."""
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path, **{"Test subject": _high_confidence_response()})
    message = make_message(message_id="msg-1", subject="Test subject")

    with StateDB(tmp_path / "state.sqlite3") as db:
        process_tier2_message(
            message,
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(_RecordingApplier()),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            **_default_kwargs(),
        )

        entries = db.get_audit_entries(jmap_id="msg-1")

    assert len(entries) == 1
    assert entries[0].ts == "2026-08-12T10:00:00Z"
