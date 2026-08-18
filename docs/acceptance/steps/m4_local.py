"""Offline Behave bindings for M4 alert routing and desktop fallback."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from behave import given, then, when

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.alerts.desktop import DesktopAlerter
from spork.core.context.clients.null import NullContextProvider
from spork.core.llm.clients.recorded import RecordedLLMClient
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2 import process_tier2_message
from spork.core.providers.file.provider import FileProvider
from spork.core.rules.schema import Action, Condition, Rule
from spork.core.state.db import StateDB


class _Alerts:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        self.calls.append({"title": title, "body": body, "url": url, "urgency": urgency})


def _setup(context: Any) -> None:
    context.tmp_dir = Path(tempfile.mkdtemp(prefix="spork-m4-local-"))
    path = context.tmp_dir / "messages.json"
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "m4-message",
                    "thread_id": "m4-thread",
                    "from_address": "boss@example.test",
                    "from_domain": "example.test",
                    "subject": "M4 local message",
                    "body_text": "Urgent local mail",
                }
            ]
        )
    )
    context.provider = FileProvider(path, context.tmp_dir / "actions.jsonl")
    context.message = context.provider.build_source().poll()[0]
    context.db = StateDB(context.tmp_dir / "state.sqlite3")
    context.alerter = _Alerts()


@given("a local M4 VIP message and an injected alerter")
def local_m4_vip(context: Any) -> None:
    _setup(context)
    context.rules = [
        Rule(
            id="vip",
            when=Condition(from_in=["boss@example.test"]),
            action=Action(type="escalate", reason="vip_sender", alert_immediately=True),
        )
    ]


@when("the local M4 message is processed by Tier 1")
def local_m4_tier1(context: Any) -> None:
    process_message(
        context.message,
        context.rules,
        default_unmatched_action=Action(type="ignore"),
        executor=ActionExecutor(context.provider.build_action_applier()),
        state_db=context.db,
        ops=PipelineObserver(context.alerter),
        now=lambda: "2026-08-18T00:00:00Z",
        new_correlation_id=lambda: "m4-correlation",
    )


@given("a local M4 high-urgency recorded verdict and an injected alerter")
def local_m4_tier2(context: Any) -> None:
    _setup(context)
    response = {
        "M4 local message": {
            "category": "needs_reply",
            "urgency": "high",
            "confidence": 0.95,
            "suggested_action": {"type": "tag", "mailbox": "Inbox"},
            "summary": "Urgent",
            "reasoning": "High urgency",
        }
    }
    response_path = context.tmp_dir / "responses.json"
    response_path.write_text(json.dumps(response))
    context.client = RecordedLLMClient(response_path)


@when("the local M4 message is processed by Tier 2")
def local_m4_process_tier2(context: Any) -> None:
    process_tier2_message(
        context.message,
        to_addresses=("me@example.test",),
        thread_prior_subject=None,
        thread_user_has_replied=False,
        available_mailboxes=("Inbox",),
        llm_client=context.client,
        executor=ActionExecutor(context.provider.build_action_applier()),
        draft_creator=context.provider.build_draft_creator(),
        state_db=context.db,
        ops=PipelineObserver(context.alerter),
        allowed_categories=["needs_reply"],
        daily_call_budget=10,
        alert_threshold=0.55,
        autoact_threshold=0.85,
        context_provider=NullContextProvider(),
        now=lambda: "2026-08-18T00:00:00Z",
        new_correlation_id=lambda: "m4-correlation",
    )


@given("a local M4 desktop alerter whose notify-send runner fails")
def local_m4_dbus_failure(context: Any) -> None:
    context.fallback = _Alerts()

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, argv, stderr="Cannot autolaunch D-Bus")

    context.desktop = DesktopAlerter(runner=runner, fallback=context.fallback)


@when("the local M4 alert is delivered")
def local_m4_deliver(context: Any) -> None:
    context.desktop.notify("Needs review", "Local alert", urgency="critical")


@then("the local M4 alerter received one alert")
def local_m4_one_alert(context: Any) -> None:
    assert len(context.alerter.calls) == 1


@then('the local M4 alert title contains "{text}"')
def local_m4_title(context: Any, text: str) -> None:
    assert text in context.alerter.calls[0]["title"]


@then("the local M4 action was applied")
def local_m4_action(context: Any) -> None:
    assert (context.tmp_dir / "actions.jsonl").exists()


@then("the local M4 alerter received one critical alert")
def local_m4_critical(context: Any) -> None:
    assert len(context.alerter.calls) == 1
    assert context.alerter.calls[0]["urgency"] == "critical"


@then("the local M4 fallback received the alert")
def local_m4_fallback(context: Any) -> None:
    assert len(context.fallback.calls) == 1
