"""Failure/edge-case tests for process_tier2_message().

Companion to test_default.py's acceptance tests.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.llm.clients.recorded import RecordedLLMClient
from spork.core.llm.validate import VerdictValidationError
from spork.core.models import NormalizedMessage
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2 import process_tier2_message
from spork.core.rules.schema import Action
from spork.core.state.db import StateDB


class _FakeAlerter:
    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        pass


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


def _write_responses(path: Path, **entries: object) -> None:
    path.write_text(json.dumps(entries))


def _response(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "category": "needs_reply",
        "urgency": "high",
        "confidence": 0.95,
        "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
        "summary": "s",
        "reasoning": "r",
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
        "ops": PipelineObserver(_FakeAlerter()),
        "now": lambda: "2026-08-12T10:00:00Z",
    }
    defaults.update(overrides)
    return defaults


def test_process_tier2_message_does_not_mark_processed_when_validation_fails(
    tmp_path: Path, make_message
) -> None:
    """A verdict naming a category this deployment never configured
    raises and aborts the run — the message is NOT marked processed,
    so it's retried next cycle rather than silently accepted with a
    bad category. Same accepted tradeoff as M2's ActionExecutionError
    (docs/DESIGN.md §10.7), not a new one."""
    responses_path = tmp_path / "responses.json"
    _write_responses(
        responses_path, **{"Test subject": _response(category="unconfigured_category")}
    )
    message = make_message(message_id="msg-1", subject="Test subject")

    with StateDB(tmp_path / "state.sqlite3") as db:
        with pytest.raises(VerdictValidationError):
            process_tier2_message(
                message,
                llm_client=RecordedLLMClient(responses_path),
                executor=ActionExecutor(_RecordingApplier()),
                draft_creator=_RecordingDraftCreator(),
                state_db=db,
                **_default_kwargs(),
            )

        assert db.has_processed("msg-1") is False


def test_process_tier2_message_applies_the_action_on_the_autoact_alert_band_too(
    tmp_path: Path, make_message
) -> None:
    """A mid-confidence verdict (autoact_alert, not autoact) still gets
    its action applied — proving the shared `act` Pipeline object
    genuinely handles both routes, not just the "autoact" one."""
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path, **{"Test subject": _response(confidence=0.7)})
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

    assert applier.calls == [(message, Action(type="tag", mailbox="Needs-Reply"))]


def test_process_tier2_message_does_not_record_llm_usage_when_budget_is_exhausted(
    tmp_path: Path, make_message
) -> None:
    """The budget-exhausted branch skips RecordLLMUsageFilter entirely
    — today's call count stays exactly what it was, not incremented
    for a call that never happened."""
    message = make_message(message_id="msg-1", subject="Test subject")

    class _NeverCalledLLMClient:
        def get_verdict(self, request: object) -> object:
            pytest.fail("should never be called when budget is exhausted")

    with StateDB(tmp_path / "state.sqlite3") as db:
        db.record_llm_call("2026-08-12", tokens_in=0, tokens_out=0)

        process_tier2_message(
            message,
            llm_client=_NeverCalledLLMClient(),
            executor=ActionExecutor(_RecordingApplier()),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            **_default_kwargs(daily_call_budget=1),
        )

        assert db.get_llm_usage("2026-08-12").calls == 1


def test_default_clock_produces_a_real_parseable_timestamp(tmp_path: Path, make_message) -> None:
    """Omitting now= (the real, non-injected path) still produces a
    genuine, parseable timestamp."""
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path, **{"Test subject": _response()})
    message = make_message(message_id="msg-1", subject="Test subject")
    kwargs = _default_kwargs()
    del kwargs["now"]

    with StateDB(tmp_path / "state.sqlite3") as db:
        verdict = process_tier2_message(
            message,
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(_RecordingApplier()),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            **kwargs,
        )

        entries = db.get_audit_entries(jmap_id="msg-1")

    assert verdict is not None
    datetime.fromisoformat(entries[0].ts)  # raises ValueError if not parseable
