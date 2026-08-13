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
from spork.daemon.state import DaemonState


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
                    rules=rules,
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
