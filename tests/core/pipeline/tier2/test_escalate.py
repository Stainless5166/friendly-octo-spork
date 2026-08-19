"""Acceptance tests for spork.core.pipeline.tier2.escalate (docs/DESIGN.md §6.2.1/§13).

escalate_message()/parse_to_addresses() were extracted from what was
spork.daemon.loop's private _escalate_to_tier2()/_parse_to_addresses()
— one real implementation, two callers (the daemon loop, and
spork reclassify). These tests exercise the extracted functions
directly, independent of either caller.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import pytest

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.alerts.log import LoggingAlerter
from spork.core.config.schema import TieringConfig
from spork.core.context.base import ContextResult, ContextSnippet
from spork.core.context.clients.null import NullContextProvider
from spork.core.llm.base import LLMResult, VerdictRequest
from spork.core.llm.clients.litellm import LiteLLMClientError
from spork.core.llm.clients.recorded import RecordedLLMClient
from spork.core.models import NormalizedMessage
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2.escalate import (
    QuarantinedMessage,
    escalate_message,
    escalate_message_or_quarantine,
    parse_to_addresses,
)
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
    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, str]] = []

    def create_draft(self, in_reply_to: NormalizedMessage, body: str) -> None:
        self.calls.append((in_reply_to, body))


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
            context_provider=NullContextProvider(),
        )

    assert verdict is not None
    assert verdict.suggested_action.mailbox == "Needs-Reply"
    assert thread_history_reader.calls == [message]
    assert mailbox_lister.calls == 1
    assert applier.calls == [(message, Action(type="tag", mailbox="Needs-Reply"))]


class _StubContextProvider:
    def __init__(self, result: ContextResult) -> None:
        self._result = result

    def get_context(self, message: NormalizedMessage) -> ContextResult:
        return self._result


class _RecordingLLMClient:
    """Wraps a real client just to capture the exact VerdictRequest it
    was called with — proves context_provider's result actually
    reached the prompt, not just that escalate_message() accepts the
    argument."""

    def __init__(self, inner: RecordedLLMClient) -> None:
        self._inner = inner
        self.last_request: VerdictRequest | None = None

    def get_verdict(self, request: VerdictRequest) -> LLMResult:
        self.last_request = request
        return self._inner.get_verdict(request)


def test_escalate_message_wires_context_provider_into_tier2(tmp_path: Path, make_message) -> None:
    """docs/DESIGN.md §10.8 (item 3): escalate_message() threads its
    context_provider argument all the way to the actual prompt, same
    depth of wiring thread_history_reader/mailbox_lister already get."""
    message = make_message(message_id="msg-1", subject="Urgent")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                "Urgent": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "ignore"},
                    "summary": "s",
                    "reasoning": "r",
                }
            }
        )
    )
    client = _RecordingLLMClient(RecordedLLMClient(responses_path))

    with StateDB(tmp_path / "state.sqlite3") as state_db:
        escalate_message(
            message,
            thread_history_reader=_RecordingThreadHistoryReader(
                ThreadContext(prior_subject=None, user_has_replied=False)
            ),
            mailbox_lister=_RecordingMailboxLister(["Inbox"]),
            llm_client=client,
            executor=ActionExecutor(_RecordingApplier()),
            draft_creator=_RecordingDraftCreator(),
            state_db=state_db,
            ops=PipelineObserver(LoggingAlerter()),
            tiering=TieringConfig(allowed_categories=["needs_reply"]),
            context_provider=_StubContextProvider(
                ContextResult(snippets=(ContextSnippet(source="notes/a.md", text="A note."),))
            ),
        )

    assert client.last_request is not None
    assert client.last_request.context_snippets == ("notes/a.md: A note.",)


def test_utc_now_iso_default_clock_is_actually_utc() -> None:
    """_utc_now_iso() (escalate_message_or_quarantine()'s default `now`
    clock) is timezone-aware UTC, not a naive local timestamp — the same
    class of gap the M7a mutation round already found in a sibling
    default clock elsewhere, caught here by a mutmut survivor that swapped
    datetime.now(UTC) for datetime.now(None) with nothing noticing."""
    from spork.core.pipeline.tier2.escalate import _utc_now_iso

    assert _utc_now_iso().endswith("+00:00")


def test_escalate_message_threads_thread_context_and_max_body_chars_into_the_request(
    tmp_path: Path, make_message
) -> None:
    """thread_prior_subject/thread_user_has_replied (from the injected
    ThreadHistoryReader) and max_body_chars (from TieringConfig) all
    reach the actual VerdictRequest sent to the model — not just the
    mailbox_lister/thread_history_reader call counts test_escalate_message_
    wires_thread_history_and_mailbox_lister_into_tier2 already proves."""
    message = make_message(message_id="msg-1", subject="Urgent", body_text="x" * 100)
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                "Urgent": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "ignore"},
                    "summary": "s",
                    "reasoning": "r",
                }
            }
        )
    )
    client = _RecordingLLMClient(RecordedLLMClient(responses_path))

    with StateDB(tmp_path / "state.sqlite3") as state_db:
        escalate_message(
            message,
            thread_history_reader=_RecordingThreadHistoryReader(
                ThreadContext(prior_subject="Re: earlier", user_has_replied=True)
            ),
            mailbox_lister=_RecordingMailboxLister(["Inbox"]),
            llm_client=client,
            executor=ActionExecutor(_RecordingApplier()),
            draft_creator=_RecordingDraftCreator(),
            state_db=state_db,
            ops=PipelineObserver(LoggingAlerter()),
            tiering=TieringConfig(allowed_categories=["needs_reply"], max_body_chars=10),
            context_provider=NullContextProvider(),
        )

    assert client.last_request is not None
    assert client.last_request.thread_prior_subject == "Re: earlier"
    assert client.last_request.thread_user_has_replied is True
    # clean_body() truncates a space-free body to exactly max_chars,
    # word-boundary logic notwithstanding, plus its truncation marker —
    # proves the *configured* 10, not process_tier2_message()'s own
    # default of 4000, actually reached BuildVerdictRequestFilter.
    assert client.last_request.cleaned_body == "x" * 10 + " ... [truncated]"


def test_escalate_message_threads_draft_creator_into_a_requested_draft(
    tmp_path: Path, make_message
) -> None:
    """The exact draft_creator instance passed in is what actually
    receives create_draft() — proven by giving the model a draft_reply
    to act on, not just by never crashing (a None draft_creator only
    fails when a draft is actually requested, which no other test here
    triggers)."""
    message = make_message(message_id="msg-1", subject="Urgent")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                "Urgent": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "ignore"},
                    "summary": "s",
                    "reasoning": "r",
                    "draft_reply": "Thanks, will look into it.",
                }
            }
        )
    )
    draft_creator = _RecordingDraftCreator()

    with StateDB(tmp_path / "state.sqlite3") as state_db:
        escalate_message(
            message,
            thread_history_reader=_RecordingThreadHistoryReader(
                ThreadContext(prior_subject=None, user_has_replied=False)
            ),
            mailbox_lister=_RecordingMailboxLister(["Inbox"]),
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(_RecordingApplier()),
            draft_creator=draft_creator,
            state_db=state_db,
            ops=PipelineObserver(LoggingAlerter()),
            tiering=TieringConfig(allowed_categories=["needs_reply"]),
            context_provider=NullContextProvider(),
        )

    assert draft_creator.calls == [(message, "Thanks, will look into it.")]


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
            context_provider=NullContextProvider(),
        )

    assert verdict is None


class _RaisingLLMClient:
    """Simulates a live LLM call that fails outright (bad JSON, API
    error) — LiteLLMClient wraps these as LiteLLMClientError."""

    def get_verdict(self, request: VerdictRequest) -> LLMResult:
        raise LiteLLMClientError("simulated live completion failure")


class _RecordingAlerter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, AlertUrgency]] = []

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        self.calls.append((title, body, urgency))


def _read_processed_record(db_path: Path, jmap_id: str) -> tuple[str | None, str | None]:
    """(tier_reached, action_taken) for `jmap_id`'s processed_messages row —
    read via a second, independent sqlite3 connection since StateDB
    exposes no getter for these two columns (write-only from every
    caller's own perspective today)."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT tier_reached, action_taken FROM processed_messages WHERE jmap_id = ?",
            (jmap_id,),
        ).fetchone()
    assert row is not None
    return row


def _base_kwargs(tmp_path: Path, message: NormalizedMessage, state_db: StateDB, alerter=None):
    return dict(
        message=message,
        thread_history_reader=_RecordingThreadHistoryReader(
            ThreadContext(prior_subject=None, user_has_replied=False)
        ),
        mailbox_lister=_RecordingMailboxLister(["Inbox"]),
        executor=ActionExecutor(_RecordingApplier()),
        draft_creator=_RecordingDraftCreator(),
        state_db=state_db,
        ops=PipelineObserver(alerter or LoggingAlerter()),
        context_provider=NullContextProvider(),
    )


def test_escalate_message_or_quarantine_passes_through_a_normal_verdict(
    tmp_path: Path, make_message
) -> None:
    """The common path is unaffected: a valid, in-set verdict comes back
    exactly as escalate_message() itself would return it."""
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
    with StateDB(tmp_path / "state.sqlite3") as state_db:
        kwargs = _base_kwargs(tmp_path, message, state_db)
        kwargs["mailbox_lister"] = _RecordingMailboxLister(["Needs-Reply", "Inbox"])
        result = escalate_message_or_quarantine(
            **kwargs,
            llm_client=RecordedLLMClient(responses_path),
            tiering=TieringConfig(allowed_categories=["needs_reply"]),
        )

    assert result is not None and not isinstance(result, QuarantinedMessage)
    assert result.suggested_action.mailbox == "Needs-Reply"


def test_escalate_message_or_quarantine_threads_draft_creator_into_a_requested_draft(
    tmp_path: Path, make_message
) -> None:
    """escalate_message_or_quarantine()'s own draft_creator kwarg reaches
    the delegated escalate_message() call unchanged — mirrors
    test_escalate_message_threads_draft_creator_into_a_requested_draft,
    but through the quarantine wrapper's own passthrough."""
    message = make_message(message_id="msg-1", subject="Urgent")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                "Urgent": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "ignore"},
                    "summary": "s",
                    "reasoning": "r",
                    "draft_reply": "Thanks, will look into it.",
                }
            }
        )
    )
    draft_creator = _RecordingDraftCreator()

    with StateDB(tmp_path / "state.sqlite3") as state_db:
        kwargs = _base_kwargs(tmp_path, message, state_db)
        kwargs["draft_creator"] = draft_creator
        escalate_message_or_quarantine(
            **kwargs,
            llm_client=RecordedLLMClient(responses_path),
            tiering=TieringConfig(allowed_categories=["needs_reply"]),
        )

    assert draft_creator.calls == [(message, "Thanks, will look into it.")]


def test_escalate_message_or_quarantine_still_returns_none_on_budget_exhausted(
    tmp_path: Path, make_message
) -> None:
    """None (budget exhausted) and QuarantinedMessage are distinct signals —
    a caller must be able to tell them apart."""
    message = make_message(message_id="msg-1", subject="Urgent")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text("{}")

    with StateDB(tmp_path / "state.sqlite3") as state_db:
        result = escalate_message_or_quarantine(
            **_base_kwargs(tmp_path, message, state_db),
            llm_client=RecordedLLMClient(responses_path),
            tiering=TieringConfig(daily_call_budget=0),
        )

    assert result is None


def test_escalate_message_or_quarantine_quarantines_an_out_of_set_category(
    tmp_path: Path, make_message
) -> None:
    """VerdictValidationError (a category outside allowed_categories) is
    quarantined, not raised: the message is marked processed (never
    retried forever, never re-burning budget) and audited — with the
    exact detail_json/tier_reached/action_taken content a human
    debugging a quarantined message would actually read, not just a
    bare "some audit entry exists"."""
    message = make_message(message_id="msg-1", subject="Urgent")
    db_path = tmp_path / "state.sqlite3"
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                "Urgent": {
                    "category": "not_a_configured_category",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "ignore"},
                    "summary": "s",
                    "reasoning": "r",
                }
            }
        )
    )

    with StateDB(db_path) as state_db:
        result = escalate_message_or_quarantine(
            **_base_kwargs(tmp_path, message, state_db),
            llm_client=RecordedLLMClient(responses_path),
            tiering=TieringConfig(allowed_categories=["needs_reply"]),
        )

        assert isinstance(result, QuarantinedMessage)
        assert state_db.has_processed("msg-1")
        entries = state_db.get_audit_entries(jmap_id="msg-1")
        quarantine_entries = [e for e in entries if e.event == "tier2_quarantined"]
        assert len(quarantine_entries) == 1
        assert quarantine_entries[0].detail_json is not None
        detail = json.loads(quarantine_entries[0].detail_json)
        assert detail == {"error_type": "VerdictValidationError", "reason": result.reason}

    tier_reached, action_taken = _read_processed_record(db_path, "msg-1")
    assert tier_reached == "tier2"
    assert action_taken == "quarantined"


def test_escalate_message_or_quarantine_quarantines_a_malformed_action(
    tmp_path: Path, make_message
) -> None:
    """ActionExecutionError (a move with no mailbox — a verdict pydantic's
    own shape check doesn't catch, since Action.mailbox is optional) is
    quarantined the same way."""
    message = make_message(message_id="msg-1", subject="Urgent")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                "Urgent": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "move"},
                    "summary": "s",
                    "reasoning": "r",
                }
            }
        )
    )

    with StateDB(tmp_path / "state.sqlite3") as state_db:
        result = escalate_message_or_quarantine(
            **_base_kwargs(tmp_path, message, state_db),
            llm_client=RecordedLLMClient(responses_path),
            tiering=TieringConfig(allowed_categories=["needs_reply"]),
        )

    assert isinstance(result, QuarantinedMessage)


def test_escalate_message_or_quarantine_quarantines_a_failed_llm_call(
    tmp_path: Path, make_message
) -> None:
    """LiteLLMClientError (the live call itself failed) is quarantined
    the same way as a malformed-but-successful response."""
    message = make_message(message_id="msg-1", subject="Urgent")

    with StateDB(tmp_path / "state.sqlite3") as state_db:
        result = escalate_message_or_quarantine(
            **_base_kwargs(tmp_path, message, state_db),
            llm_client=_RaisingLLMClient(),
            tiering=TieringConfig(allowed_categories=["needs_reply"]),
        )

    assert isinstance(result, QuarantinedMessage)


def test_escalate_message_or_quarantine_fires_a_critical_alert(
    tmp_path: Path, make_message, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    message = make_message(message_id="msg-1", subject="Urgent")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                "Urgent": {
                    "category": "not_a_configured_category",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "ignore"},
                    "summary": "s",
                    "reasoning": "r",
                }
            }
        )
    )
    alerter = _RecordingAlerter()

    with StateDB(tmp_path / "state.sqlite3") as state_db:
        result = escalate_message_or_quarantine(
            **_base_kwargs(tmp_path, message, state_db, alerter=alerter),
            llm_client=RecordedLLMClient(responses_path),
            tiering=TieringConfig(allowed_categories=["needs_reply"]),
        )

    assert isinstance(result, QuarantinedMessage)
    # Exact title/body content, not just that *an* alert fired — the
    # correlation_id (PipelineObserver.trace()'s record) is a real
    # uuid4 hex, distinguishable from a mutant that passes None through.
    assert alerter.calls == [
        (
            "Tier 2 verdict quarantined",
            f"{message.subject!r} from {message.from_address}: {result.reason}",
            "critical",
        )
    ]
    # The pipeline itself traces several earlier events (TimestampFilter,
    # CorrelationIdFilter, ...) under its own meta.correlation_id first —
    # the "Tier 2 verdict quarantined" record is escalate_message_or_
    # quarantine()'s own ops.alert() call, always the last one logged.
    correlation_id = caplog.records[-1].correlation_id
    assert isinstance(correlation_id, str)
    assert len(correlation_id) == 32
    int(correlation_id, 16)  # a real hex string, not a stringified None


def test_escalate_message_or_quarantine_does_not_catch_a_real_pipeline_bug(
    tmp_path: Path, make_message
) -> None:
    """A MissingMetaError (a genuine wiring bug, not a bad model
    response) is deliberately not in QUARANTINABLE_ERRORS — it still
    propagates rather than being silently absorbed as if it were a
    quarantinable model-output failure."""
    from spork.core.pipeline.meta import MissingMetaError

    class _BrokenMailboxLister:
        def list_mailboxes(self) -> list[str]:
            raise MissingMetaError("simulated real pipeline bug")

    message = make_message(message_id="msg-1", subject="Urgent")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text("{}")

    with (
        StateDB(tmp_path / "state.sqlite3") as state_db,
        pytest.raises(MissingMetaError),
    ):
        escalate_message_or_quarantine(
            message=message,
            thread_history_reader=_RecordingThreadHistoryReader(
                ThreadContext(prior_subject=None, user_has_replied=False)
            ),
            mailbox_lister=_BrokenMailboxLister(),
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(_RecordingApplier()),
            draft_creator=_RecordingDraftCreator(),
            state_db=state_db,
            ops=PipelineObserver(LoggingAlerter()),
            tiering=TieringConfig(allowed_categories=["needs_reply"]),
            context_provider=NullContextProvider(),
        )
