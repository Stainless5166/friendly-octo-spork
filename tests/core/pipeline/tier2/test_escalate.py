"""Acceptance tests for spork.core.pipeline.tier2.escalate (docs/DESIGN.md §6.2.1/§13).

escalate_message()/parse_to_addresses() were extracted from what was
spork.daemon.loop's private _escalate_to_tier2()/_parse_to_addresses()
— one real implementation, two callers (the daemon loop, and
spork reclassify). These tests exercise the extracted functions
directly, independent of either caller.
"""

from __future__ import annotations

import json
from pathlib import Path

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.log import LoggingAlerter
from spork.core.config.schema import TieringConfig
from spork.core.llm.clients.recorded import RecordedLLMClient
from spork.core.models import NormalizedMessage
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2.escalate import escalate_message, parse_to_addresses
from spork.core.providers.base import ThreadContext
from spork.core.rules.schema import Action
from spork.core.state.db import StateDB


def test_parse_to_addresses_splits_and_strips_a_comma_separated_to_header(make_message) -> None:
    message = make_message(headers={"To": "a@example.com, b@example.com ,c@example.com"})

    assert parse_to_addresses(message) == ("a@example.com", "b@example.com", "c@example.com")


def test_parse_to_addresses_returns_empty_tuple_when_no_to_header(make_message) -> None:
    message = make_message(headers={})

    assert parse_to_addresses(message) == ()


class _RecordingThreadHistoryReader:
    def __init__(self, context: ThreadContext) -> None:
        self._context = context
        self.calls: list[NormalizedMessage] = []

    def get_thread_context(self, message: NormalizedMessage) -> ThreadContext:
        self.calls.append(message)
        return self._context


class _RecordingMailboxLister:
    def __init__(self, mailboxes: list[str]) -> None:
        self._mailboxes = mailboxes
        self.calls = 0

    def list_mailboxes(self) -> list[str]:
        self.calls += 1
        return self._mailboxes


class _RecordingApplier:
    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, Action]] = []

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self.calls.append((message, action))


class _RecordingDraftCreator:
    def create_draft(self, in_reply_to: NormalizedMessage, body: str) -> None:
        pass


def test_escalate_message_wires_thread_history_and_mailbox_lister_into_tier2(
    tmp_path: Path, make_message
) -> None:
    """escalate_message() calls both Provider-supplied reads with the
    escalated message, and the resulting Verdict's action is actually
    applied — proof it's a real end-to-end call into
    process_tier2_message(), not just a passthrough."""
    message = make_message(message_id="msg-1", subject="Urgent")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                "Urgent": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
                    "summary": "s",
                    "reasoning": "r",
                }
            }
        )
    )
    thread_history_reader = _RecordingThreadHistoryReader(
        ThreadContext(prior_subject="Re: earlier", user_has_replied=True)
    )
    mailbox_lister = _RecordingMailboxLister(["Needs-Reply", "Inbox"])
    applier = _RecordingApplier()

    with StateDB(tmp_path / "state.sqlite3") as state_db:
        verdict = escalate_message(
            message,
            thread_history_reader=thread_history_reader,
            mailbox_lister=mailbox_lister,
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(applier),
            draft_creator=_RecordingDraftCreator(),
            state_db=state_db,
            ops=PipelineObserver(LoggingAlerter()),
            tiering=TieringConfig(allowed_categories=["needs_reply"]),
        )

    assert verdict is not None
    assert verdict.suggested_action.mailbox == "Needs-Reply"
    assert thread_history_reader.calls == [message]
    assert mailbox_lister.calls == 1
    assert applier.calls == [(message, Action(type="tag", mailbox="Needs-Reply"))]


def test_escalate_message_returns_none_when_the_daily_budget_is_exhausted(
    tmp_path: Path, make_message
) -> None:
    """escalate_message() passes process_tier2_message()'s None-on-
    budget-exhausted result straight through, rather than assuming a
    Verdict always comes back."""
    message = make_message(message_id="msg-1", subject="Urgent")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text("{}")

    with StateDB(tmp_path / "state.sqlite3") as state_db:
        verdict = escalate_message(
            message,
            thread_history_reader=_RecordingThreadHistoryReader(
                ThreadContext(prior_subject=None, user_has_replied=False)
            ),
            mailbox_lister=_RecordingMailboxLister([]),
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(_RecordingApplier()),
            draft_creator=_RecordingDraftCreator(),
            state_db=state_db,
            ops=PipelineObserver(LoggingAlerter()),
            tiering=TieringConfig(daily_call_budget=0),
        )

    assert verdict is None
