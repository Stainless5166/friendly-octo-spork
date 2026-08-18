"""Offline Behave bindings for M3's recorded Tier 2 pipeline."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from behave import given, then, when

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.context.clients.null import NullContextProvider
from spork.core.llm.clients.recorded import RecordedLLMClient
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2 import process_tier2_message
from spork.core.providers.file.provider import FileProvider
from spork.core.state.db import StateDB


class _RecordingAlerter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        self.calls.append({"title": title, "body": body, "url": url, "urgency": urgency})


def _base_response(**overrides: object) -> dict[str, object]:
    response: dict[str, object] = {
        "category": "needs_reply",
        "urgency": "medium",
        "confidence": 0.95,
        "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
        "summary": "Local response",
        "reasoning": "Recorded acceptance response",
    }
    response.update(overrides)
    return response


def _setup(
    context: Any,
    response: dict[str, object],
    *,
    budget: int = 10,
    mailboxes: list[str] | None = None,
) -> None:
    context.tmp_dir = Path(tempfile.mkdtemp(prefix="spork-m3-local-"))
    messages = context.tmp_dir / "messages.json"
    messages.write_text(
        json.dumps(
            [
                {
                    "message_id": "m3-message",
                    "thread_id": "m3-thread",
                    "from_address": "sender@example.test",
                    "from_domain": "example.test",
                    "subject": "M3 local message",
                    "body_text": "Please reply.",
                }
            ]
        )
    )
    context.provider = FileProvider(
        messages,
        context.tmp_dir / "actions.jsonl",
        drafts_log_path=context.tmp_dir / "drafts.jsonl",
    )
    context.message = context.provider.build_source().poll()[0]
    context.response_path = context.tmp_dir / "responses.json"
    context.response_path.write_text(json.dumps({"M3 local message": response}))
    context.client = RecordedLLMClient(context.response_path)
    context.called = 0
    original = context.client.get_verdict

    def counted(request: Any) -> Any:
        context.called += 1
        return original(request)

    context.client.get_verdict = counted  # type: ignore[method-assign]
    context.db = StateDB(context.tmp_dir / "state.sqlite3")
    if budget == 0:
        context.db.record_llm_call("2026-08-18", tokens_in=0, tokens_out=0)
    context.alerter = _RecordingAlerter()
    context.mailboxes = mailboxes or ["Inbox", "Needs-Reply"]
    context.error = None


def _run(context: Any) -> None:
    try:
        context.verdict = process_tier2_message(
            context.message,
            to_addresses=("me@example.test",),
            thread_prior_subject=None,
            thread_user_has_replied=False,
            available_mailboxes=context.mailboxes,
            llm_client=context.client,
            executor=ActionExecutor(context.provider.build_action_applier()),
            draft_creator=context.provider.build_draft_creator(),
            state_db=context.db,
            ops=PipelineObserver(context.alerter),
            allowed_categories=["needs_reply", "fyi"],
            daily_call_budget=1 if getattr(context, "budget_exhausted", False) else 10,
            alert_threshold=0.55,
            autoact_threshold=0.85,
            context_provider=NullContextProvider(),
            now=lambda: "2026-08-18T00:00:00Z",
            new_correlation_id=lambda: "m3-correlation",
        )
    except Exception as exc:  # noqa: BLE001 - failure-safety scenario asserts the boundary
        context.error = exc


@given("a local M3 recorded response with confidence {confidence:f}")
def local_m3_confidence(context: Any, confidence: float) -> None:
    _setup(context, _base_response(confidence=confidence))


@given("a local M3 recorded response and an exhausted daily budget")
def local_m3_budget(context: Any) -> None:
    _setup(context, _base_response())
    context.budget_exhausted = True
    context.db.record_llm_call("2026-08-18", tokens_in=0, tokens_out=0)


@given("a local M3 recorded response with draft text")
def local_m3_draft(context: Any) -> None:
    _setup(context, _base_response(draft_reply="Friday at 2pm works."))


@given("a local M3 recorded response targeting an unavailable mailbox")
def local_m3_invalid_mailbox(context: Any) -> None:
    _setup(context, _base_response(suggested_action={"type": "tag", "mailbox": "No-Such-Mailbox"}))


@when("the local M3 message is processed by Tier 2")
def local_m3_process(context: Any) -> None:
    _run(context)


@when("the local M3 message is processed by Tier 2 and validation fails")
def local_m3_process_invalid(context: Any) -> None:
    _run(context)
    assert context.error is not None


@then("the local M3 message is marked processed")
def local_m3_processed(context: Any) -> None:
    assert context.db.has_processed("m3-message")


@then("the local M3 message is not marked processed")
def local_m3_not_processed(context: Any) -> None:
    assert not context.db.has_processed("m3-message")


@then("the local M3 action log is empty")
def local_m3_actions_empty(context: Any) -> None:
    assert not (context.tmp_dir / "actions.jsonl").exists()


@then("the local M3 action log contains one tag")
def local_m3_one_tag(context: Any) -> None:
    entries = [
        json.loads(line) for line in (context.tmp_dir / "actions.jsonl").read_text().splitlines()
    ]
    assert len(entries) == 1
    assert entries[0]["action_type"] == "tag"


@then("the local M3 action and drafts logs are empty")
def local_m3_logs_empty(context: Any) -> None:
    local_m3_actions_empty(context)
    assert not (context.tmp_dir / "drafts.jsonl").exists()


@then("the local M3 alert count is 1")
def local_m3_one_alert(context: Any) -> None:
    assert len(context.alerter.calls) == 1


@then("the local M3 recorded client is not called")
def local_m3_not_called(context: Any) -> None:
    assert context.called == 0


@then('the local M3 alert urgency is "{urgency}"')
def local_m3_urgency(context: Any, urgency: str) -> None:
    assert context.alerter.calls[0]["urgency"] == urgency


@then("the local M3 drafts log contains the reply")
def local_m3_draft_log(context: Any) -> None:
    entries = [
        json.loads(line) for line in (context.tmp_dir / "drafts.jsonl").read_text().splitlines()
    ]
    assert entries[0]["body"] == "Friday at 2pm works."
