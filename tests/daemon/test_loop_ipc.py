"""Acceptance tests for run_daemon()'s IPC server + pause/resume (docs/DESIGN.md §6.2.2).

Companion to test_loop.py's Tier-1-processing tests — these exercise
the second task inside run_daemon()'s asyncio.TaskGroup: a real
IpcServer, reachable over a real Unix socket, sharing DaemonState with
the message loop.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.log import LoggingAlerter
from spork.core.config.schema import BackendSpec, SporkConfig, TieringConfig
from spork.core.ipc.client import send_request
from spork.core.llm.base import Verdict, VerdictRequest
from spork.core.models import NormalizedMessage
from spork.core.pipeline.observer import PipelineObserver
from spork.core.providers.base import ThreadContext
from spork.core.rules.schema import Action, Condition, Rule
from spork.core.state.db import StateDB
from spork.daemon.loop import _run_message_loop, run_daemon
from spork.daemon.state import DaemonState, RulesState


class _UnusedLLMClient:
    """Fails loudly if called — none of this file's rules escalate."""

    def get_verdict(self, request: VerdictRequest) -> Verdict:
        raise AssertionError("get_verdict() should not be called in this test")


class _UnusedDraftCreator:
    def create_draft(self, in_reply_to: NormalizedMessage, body: str) -> None:
        raise AssertionError("create_draft() should not be called in this test")


class _UnusedThreadHistoryReader:
    def get_thread_context(self, message: NormalizedMessage) -> ThreadContext:
        raise AssertionError("get_thread_context() should not be called in this test")


class _UnusedMailboxLister:
    def list_mailboxes(self) -> Sequence[str]:
        raise AssertionError("list_mailboxes() should not be called in this test")


def _write_messages(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "s",
                    "body_text": "b",
                }
            ]
        )
    )


def _write_rules(path: Path) -> None:
    path.write_text(
        """
        [[rule]]
        id = "catch-all"
        when = { always = true }
        action = { type = "tag", mailbox = "Inbox" }
        """
    )


def _config(tmp_path: Path) -> SporkConfig:
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path)
    rules_path = tmp_path / "rules.toml"
    _write_rules(rules_path)
    # RecordedLLMClient with no recorded responses — real and
    # constructible (unlike the old "unused:Unused" placeholder,
    # run_daemon() now always constructs an LLMClient), but never
    # actually called since this file's catch-all rule always tags,
    # never escalates.
    responses_path = tmp_path / "responses.json"
    responses_path.write_text("{}")

    return SporkConfig(
        provider=BackendSpec(
            spec="spork.core.providers.file.provider:FileProvider",
            kwargs={
                "messages_path": str(messages_path),
                "actions_log_path": str(tmp_path / "actions.jsonl"),
            },
        ),
        llm=BackendSpec(
            spec="spork.core.llm.clients.recorded:RecordedLLMClient",
            kwargs={"responses_path": str(responses_path)},
        ),
        alerts=BackendSpec(spec="spork.core.alerts.log:LoggingAlerter"),
        rules_path=rules_path,
        db_path=tmp_path / "state.sqlite3",
        socket_path=tmp_path / "sporkd.sock",
    )


def test_run_daemon_serves_status_over_the_socket(tmp_path: Path) -> None:
    """A real status request, over a real socket, against a real
    running run_daemon() — paused starts False, started_at is set."""
    config = _config(tmp_path)

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            run_daemon(config, stop_event=stop_event, idle_delay_seconds=0.02)
        )
        await asyncio.sleep(0.1)

        response = await asyncio.to_thread(send_request, config.socket_path, "status")

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert response.ok is True
        assert response.data["paused"] is False
        assert response.data["started_at"]

    asyncio.run(_body())


def test_run_daemon_pause_then_status_reports_paused(tmp_path: Path) -> None:
    """pause -> status shows paused=True; resume -> status shows
    paused=False again — the full round trip through the socket."""
    config = _config(tmp_path)

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            run_daemon(config, stop_event=stop_event, idle_delay_seconds=0.02)
        )
        await asyncio.sleep(0.1)

        pause_response = await asyncio.to_thread(send_request, config.socket_path, "pause")
        status_response = await asyncio.to_thread(send_request, config.socket_path, "status")
        resume_response = await asyncio.to_thread(send_request, config.socket_path, "resume")
        status_after_resume = await asyncio.to_thread(send_request, config.socket_path, "status")

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert pause_response.data == {"paused": True}
        assert status_response.data["paused"] is True
        assert resume_response.data == {"paused": False}
        assert status_after_resume.data["paused"] is False

    asyncio.run(_body())


def test_run_daemon_still_processes_messages_while_serving_ipc(tmp_path: Path) -> None:
    """Both tasks in the TaskGroup genuinely coexist: a status request
    doesn't block or replace Tier 1 message processing."""
    config = _config(tmp_path)

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            run_daemon(config, stop_event=stop_event, idle_delay_seconds=0.02)
        )
        await asyncio.sleep(0.2)

        await asyncio.to_thread(send_request, config.socket_path, "status")

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        with StateDB(config.db_path) as db:
            assert db.has_processed("msg-1") is True

    asyncio.run(_body())


def _message(message_id: str) -> NormalizedMessage:
    return NormalizedMessage(
        message_id=message_id,
        thread_id=f"thread-{message_id}",
        from_address="a@example.com",
        from_domain="example.com",
        subject="s",
        body_text="b",
        headers={},
        mailbox_ids=(),
    )


class _CountingSource:
    def __init__(self, messages: Sequence[NormalizedMessage]) -> None:
        self._messages = list(messages)
        self.calls = 0

    def poll(self) -> Sequence[NormalizedMessage]:
        self.calls += 1
        batch, self._messages = self._messages, []
        return batch


def test_run_message_loop_never_polls_while_paused(tmp_path: Path) -> None:
    """While daemon_state.paused is True from the start, poll() is
    never called — proves pause is a real behavioral skip, not just a
    flag nobody reads."""
    source = _CountingSource([_message("msg-1")])
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="tag", mailbox="X"))]

    async def _body() -> None:
        stop_event = asyncio.Event()
        daemon_state = DaemonState(paused=True)

        async def _stop_after(seconds: float) -> None:
            await asyncio.sleep(seconds)
            stop_event.set()

        with StateDB(tmp_path / "state.sqlite3") as state_db:
            await asyncio.gather(
                _run_message_loop(
                    source=source,
                    rules_state=RulesState(rules=rules),
                    default_unmatched_action=Action(type="escalate"),
                    executor=ActionExecutor(_NoopApplier()),
                    state_db=state_db,
                    ops=PipelineObserver(LoggingAlerter()),
                    classifier=None,
                    llm_client=_UnusedLLMClient(),
                    draft_creator=_UnusedDraftCreator(),
                    thread_history_reader=_UnusedThreadHistoryReader(),
                    mailbox_lister=_UnusedMailboxLister(),
                    tiering=TieringConfig(),
                    daemon_state=daemon_state,
                    stop_event=stop_event,
                    idle_delay_seconds=0.02,
                ),
                _stop_after(0.1),
            )

        assert source.calls == 0

    asyncio.run(_body())


class _NoopApplier:
    def apply(self, message: NormalizedMessage, action: Action) -> None:
        pass


def test_run_daemon_reload_with_a_valid_rewritten_rules_file_returns_ok(tmp_path: Path) -> None:
    """A valid rules.toml, rewritten after sporkd started: the reload
    command re-reads it and reports success."""
    config = _config(tmp_path)

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            run_daemon(config, stop_event=stop_event, idle_delay_seconds=0.02)
        )
        await asyncio.sleep(0.1)

        config.rules_path.write_text(
            """
            [[rule]]
            id = "catch-all"
            when = { always = true }
            action = { type = "move", mailbox = "Archive" }
            """
        )
        response = await asyncio.to_thread(send_request, config.socket_path, "reload")

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert response.ok is True

    asyncio.run(_body())


def test_run_daemon_reload_with_invalid_rules_returns_ok_false_and_keeps_running(
    tmp_path: Path,
) -> None:
    """A hand-edit that breaks rules.toml: reload reports failure
    (ok=False, a real RulesLoadError message), but the daemon itself
    keeps running rather than crashing — proven by a subsequent status
    request over the same socket still succeeding."""
    config = _config(tmp_path)

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            run_daemon(config, stop_event=stop_event, idle_delay_seconds=0.02)
        )
        await asyncio.sleep(0.1)

        config.rules_path.write_text("this is not [ valid toml")
        reload_response = await asyncio.to_thread(send_request, config.socket_path, "reload")
        status_response = await asyncio.to_thread(send_request, config.socket_path, "status")

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

        assert reload_response.ok is False
        assert reload_response.error
        assert status_response.ok is True

    asyncio.run(_body())


class _MutatingSource:
    """Test-only Source: its second poll() call mutates rules_state.rules
    as a side effect, standing in for a `reload` IPC command landing
    between two poll cycles without needing real async timing
    coordination — the production reload path (an IpcServer handler on
    the event-loop thread) is exercised for real by the two tests above;
    this one isolates _run_message_loop()'s "read rules_state.rules
    fresh every poll iteration" contract on its own."""

    def __init__(
        self,
        batches: Sequence[Sequence[NormalizedMessage]],
        *,
        rules_state: RulesState,
        new_rules: Sequence[Rule],
    ) -> None:
        self._batches = list(batches)
        self._rules_state = rules_state
        self._new_rules = new_rules
        self.calls = 0

    def poll(self) -> Sequence[NormalizedMessage]:
        self.calls += 1
        if self.calls == 2:
            self._rules_state.rules = self._new_rules
        if self._batches:
            return self._batches.pop(0)
        return []


def test_run_message_loop_picks_up_a_reloaded_rules_list_on_the_next_poll_iteration(
    tmp_path: Path,
) -> None:
    """The first batch's message is tagged Inbox (the old rule); the
    second batch's message is moved to Archive (the new rule) — proof
    that rules_state.rules is read fresh per poll iteration, not
    captured once when _run_message_loop() started."""
    old_rules = [
        Rule(id="r1", when=Condition(always=True), action=Action(type="tag", mailbox="Inbox"))
    ]
    new_rules = [
        Rule(id="r1", when=Condition(always=True), action=Action(type="move", mailbox="Archive"))
    ]
    rules_state = RulesState(rules=old_rules)
    applier = _RecordingApplier()
    source = _MutatingSource(
        [[_message("first")], [_message("second")]], rules_state=rules_state, new_rules=new_rules
    )

    async def _body() -> None:
        stop_event = asyncio.Event()

        async def _stop_after(seconds: float) -> None:
            await asyncio.sleep(seconds)
            stop_event.set()

        with StateDB(tmp_path / "state.sqlite3") as state_db:
            await asyncio.gather(
                _run_message_loop(
                    source=source,
                    rules_state=rules_state,
                    default_unmatched_action=Action(type="escalate"),
                    executor=ActionExecutor(applier),
                    state_db=state_db,
                    ops=PipelineObserver(LoggingAlerter()),
                    classifier=None,
                    llm_client=_UnusedLLMClient(),
                    draft_creator=_UnusedDraftCreator(),
                    thread_history_reader=_UnusedThreadHistoryReader(),
                    mailbox_lister=_UnusedMailboxLister(),
                    tiering=TieringConfig(),
                    daemon_state=DaemonState(),
                    stop_event=stop_event,
                    idle_delay_seconds=0.02,
                ),
                _stop_after(0.15),
            )

        assert applier.applied == [
            ("first", "tag", "Inbox"),
            ("second", "move", "Archive"),
        ]

    asyncio.run(_body())


class _RecordingApplier:
    def __init__(self) -> None:
        self.applied: list[tuple[str, str, str | None]] = []

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self.applied.append((message.message_id, action.type, action.mailbox))
