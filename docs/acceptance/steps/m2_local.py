"""Offline Behave bindings for M2's deterministic pipeline contracts."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from behave import given, then, when

from spork.core.actions.executor import ActionExecutor
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.providers.file.provider import FileProvider
from spork.core.rules.schema import Action, Condition, Rule
from spork.core.state.db import StateDB


class _QuietAlerter:
    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: str = "normal"
    ) -> None:
        del title, body, url, urgency


class _FailOnceApplier:
    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.failed = False

    def apply(self, message: Any, action: Action) -> None:
        if not self.failed:
            self.failed = True
            raise OSError("transient local action failure")
        self.inner.apply(message, action)


def _setup(context: Any, *, transient: bool = False) -> None:
    context.tmp_dir = Path(tempfile.mkdtemp(prefix="spork-m2-local-"))
    messages = context.tmp_dir / "messages.json"
    messages.write_text(
        json.dumps(
            [
                {
                    "message_id": "m2-message",
                    "thread_id": "m2-thread",
                    "from_address": "alerts@example.test",
                    "from_domain": "example.test",
                    "subject": "M2 local message",
                    "body_text": "Local acceptance message",
                }
            ]
        )
    )
    context.provider = FileProvider(messages, context.tmp_dir / "actions.jsonl")
    context.message = context.provider.build_source().poll()[0]
    context.db = StateDB(context.tmp_dir / "state.sqlite3")
    context.rules = [
        Rule(
            id="specific",
            when=Condition(from_in=["alerts@example.test"]),
            action=Action(type="move", mailbox="Reading"),
        ),
        Rule(
            id="catchall", when=Condition(always=True), action=Action(type="move", mailbox="Later")
        ),
    ]
    applier = context.provider.build_action_applier()
    context.executor = ActionExecutor(_FailOnceApplier(applier) if transient else applier)


def _run(context: Any) -> None:
    context.error = None
    try:
        context.verdict = process_message(
            context.message,
            context.rules,
            default_unmatched_action=Action(type="ignore"),
            executor=context.executor,
            state_db=context.db,
            ops=PipelineObserver(_QuietAlerter()),
            now=lambda: "2026-08-18T00:00:00Z",
            new_correlation_id=lambda: "m2-correlation",
        )
    except Exception as exc:  # noqa: BLE001 - acceptance records the retryable failure
        context.error = exc


@given("a local M2 FileProvider fixture with a message matching two rules")
def local_m2_two_rules(context: Any) -> None:
    _setup(context)


@given("a local M2 FileProvider fixture with a transiently failing action applier")
def local_m2_transient_action(context: Any) -> None:
    _setup(context, transient=True)


@when("the local M2 message is processed by Tier 1")
def local_m2_process(context: Any) -> None:
    _run(context)


@when("the local M2 message is attempted and the action fails")
def local_m2_first_attempt(context: Any) -> None:
    _run(context)
    assert context.error is not None


@when("the local M2 message is attempted again")
def local_m2_retry(context: Any) -> None:
    _run(context)
    assert context.error is None


@then('the local M2 action log contains one move to "{mailbox}"')
def local_m2_action_log(context: Any, mailbox: str) -> None:
    entries = [
        json.loads(line) for line in (context.tmp_dir / "actions.jsonl").read_text().splitlines()
    ]
    assert entries == [{"message_id": "m2-message", "action_type": "move", "mailbox": mailbox}]


@then("the local M2 verdict identifies the specific rule")
def local_m2_verdict(context: Any) -> None:
    assert context.verdict.matched_rule_id == "specific"


@then("the local M2 message is marked processed")
def local_m2_processed(context: Any) -> None:
    assert context.db.has_processed("m2-message")


@then("the local M2 message is not marked processed")
def local_m2_not_processed(context: Any) -> None:
    assert not context.db.has_processed("m2-message")


@then("the local M2 action succeeds once")
def local_m2_action_once(context: Any) -> None:
    lines = (context.tmp_dir / "actions.jsonl").read_text().splitlines()
    assert len(lines) == 1
