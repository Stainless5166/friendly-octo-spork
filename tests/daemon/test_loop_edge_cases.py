"""Failure/edge-case tests for spork.daemon.loop.

Companion to test_loop.py's acceptance tests. A few of these go
through `_run_message_loop` directly (bypassing `run_daemon()`'s
config-driven wiring) — the underscore marks it as an internal
composition detail, not a stable public API, but the stop-mid-batch
and no-busy-loop contracts are important enough to test precisely,
and `run_daemon()`'s only entry points (a `SporkConfig`) don't give
tests the fine-grained control (a custom `Source`/`ActionApplier`)
these two need.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Sequence
from pathlib import Path

import pytest

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.alerts.log import LoggingAlerter
from spork.core.config.schema import BackendSpec, SporkConfig, TieringConfig
from spork.core.llm.base import LLMResult, VerdictRequest
from spork.core.llm.clients.recorded import UnrecordedResponseError
from spork.core.models import NormalizedMessage
from spork.core.pipeline.observer import PipelineObserver
from spork.core.providers.base import ThreadContext
from spork.core.rules.loader import RulesLoadError
from spork.core.rules.schema import Action, Condition, Rule
from spork.core.sources.base import CheckpointedSource, MessageBatch
from spork.core.state.db import StateDB
from spork.daemon.loop import _check_daily_budget_alert, _run_message_loop, run_daemon
from spork.daemon.state import DaemonState, RulesState


class _UnusedLLMClient:
    """Fails loudly if called — every test that constructs this uses
    rules that only ever produce a terminal action, never "escalate",
    so Tier 2 should never be reached."""

    def get_verdict(self, request: VerdictRequest) -> LLMResult:
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


def _minimal_config(tmp_path: Path, *, rules_path: Path) -> SporkConfig:
    messages_path = tmp_path / "messages.json"
    messages_path.write_text(json.dumps([]))

    return SporkConfig(
        provider=BackendSpec(
            spec="spork.core.providers.file.provider:FileProvider",
            kwargs={
                "messages_path": str(messages_path),
                "actions_log_path": str(tmp_path / "actions.jsonl"),
            },
        ),
        llm=BackendSpec(spec="unused:Unused"),
        alerts=BackendSpec(spec="spork.core.alerts.log:LoggingAlerter"),
        rules_path=rules_path,
        db_path=tmp_path / "state.sqlite3",
        socket_path=tmp_path / "sporkd.sock",
    )


class _CountingEmptySource:
    """A Source that's always already caught up — the exhausted-
    FileProvider-after-its-first-batch scenario, without needing a
    real FileProvider to reach that state."""

    def __init__(self) -> None:
        self.calls = 0

    def poll(self) -> Sequence[NormalizedMessage]:
        self.calls += 1
        return []


class _StoppingApplier:
    """Sets `stop_event` as a side effect of applying the first
    action, so a test can assert nothing after that point runs."""

    def __init__(self, stop_event: asyncio.Event) -> None:
        self._stop_event = stop_event
        self.applied: list[str] = []

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self.applied.append(message.message_id)
        self._stop_event.set()


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


class _TwoMessageSource:
    """Returns one fixed two-message batch, then settles empty."""

    def __init__(self, messages: Sequence[NormalizedMessage]) -> None:
        self._messages = list(messages)

    def poll(self) -> Sequence[NormalizedMessage]:
        batch, self._messages = self._messages, []
        return batch


class _CheckpointSource:
    """Returns one checkpointed batch, then stops after acknowledgement."""

    def __init__(self, messages: Sequence[NormalizedMessage], stop_event: asyncio.Event) -> None:
        self._batch = list(messages)
        self._stop_event = stop_event
        self.calls = 0

    def poll_batch(self) -> MessageBatch:
        self.calls += 1
        if self.calls == 1:
            return MessageBatch(messages=self._batch, checkpoint="state-2")
        self._stop_event.set()
        return MessageBatch(messages=(), checkpoint="state-2")

    def poll(self) -> Sequence[NormalizedMessage]:
        return self.poll_batch().messages


class _EmptyCheckpointSource:
    def __init__(self, stop_event: asyncio.Event) -> None:
        self._stop_event = stop_event
        self.calls = 0

    def poll_batch(self) -> MessageBatch:
        self.calls += 1
        if self.calls > 1:
            self._stop_event.set()
        return MessageBatch(messages=(), checkpoint=f"state-{self.calls}")

    def poll(self) -> Sequence[NormalizedMessage]:
        return self.poll_batch().messages


class _FailingApplier:
    def apply(self, message: NormalizedMessage, action: Action) -> None:
        raise RuntimeError("action failed")


async def _run_checkpoint_loop(
    source: CheckpointedSource,
    state_db: StateDB,
    stop_event: asyncio.Event,
    *,
    executor: ActionExecutor,
) -> None:
    await _run_message_loop(
        source=source,
        rules_state=RulesState(
            rules=[
                Rule(id="r1", when=Condition(always=True), action=Action(type="tag", mailbox="X"))
            ]
        ),
        default_unmatched_action=Action(type="escalate"),
        executor=executor,
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
        idle_delay_seconds=0.01,
        cursor_account_id="account-1",
    )


def test_checkpoint_is_acknowledged_after_the_whole_batch_succeeds(tmp_path: Path) -> None:
    async def _body() -> None:
        stop_event = asyncio.Event()
        source = _CheckpointSource([_message("msg-1")], stop_event)
        with StateDB(tmp_path / "state.sqlite3") as state_db:
            await _run_checkpoint_loop(
                source,
                state_db,
                stop_event,
                executor=ActionExecutor(_StoppingApplier(asyncio.Event())),
            )
            assert state_db.get_cursor("account-1") == "state-2"

    asyncio.run(_body())


def test_checkpoint_is_not_acknowledged_when_processing_fails(tmp_path: Path) -> None:
    async def _body() -> None:
        stop_event = asyncio.Event()
        source = _CheckpointSource([_message("msg-1")], stop_event)
        with StateDB(tmp_path / "state.sqlite3") as state_db:
            with pytest.raises(RuntimeError, match="action failed"):
                await _run_checkpoint_loop(
                    source,
                    state_db,
                    stop_event,
                    executor=ActionExecutor(_FailingApplier()),
                )
            assert state_db.get_cursor("account-1") is None

    asyncio.run(_body())


def test_checkpoint_is_not_acknowledged_when_shutdown_interrupts_a_batch(
    tmp_path: Path,
) -> None:
    async def _body() -> None:
        stop_event = asyncio.Event()
        source = _CheckpointSource([_message("msg-1"), _message("msg-2")], stop_event)
        with StateDB(tmp_path / "state.sqlite3") as state_db:
            await _run_checkpoint_loop(
                source,
                state_db,
                stop_event,
                executor=ActionExecutor(_StoppingApplier(stop_event)),
            )
            assert state_db.get_cursor("account-1") is None

    asyncio.run(_body())


def test_empty_checkpointed_batches_are_acknowledged(tmp_path: Path) -> None:
    async def _body() -> None:
        stop_event = asyncio.Event()
        source = _EmptyCheckpointSource(stop_event)
        with StateDB(tmp_path / "state.sqlite3") as state_db:
            await _run_checkpoint_loop(
                source,
                state_db,
                stop_event,
                executor=ActionExecutor(_FailingApplier()),
            )
            assert state_db.get_cursor("account-1") == "state-2"

    asyncio.run(_body())


def test_failed_batch_leaves_the_previous_cursor_for_a_restart(tmp_path: Path) -> None:
    async def _body() -> None:
        stop_event = asyncio.Event()
        source = _CheckpointSource([_message("msg-1")], stop_event)
        with StateDB(tmp_path / "state.sqlite3") as state_db:
            state_db.set_cursor("account-1", "state-1")
            with pytest.raises(RuntimeError, match="action failed"):
                await _run_checkpoint_loop(
                    source,
                    state_db,
                    stop_event,
                    executor=ActionExecutor(_FailingApplier()),
                )
            assert state_db.get_cursor("account-1") == "state-1"

    asyncio.run(_body())


def test_run_message_loop_stops_mid_batch_without_processing_the_rest(
    tmp_path: Path,
) -> None:
    """stop_event set while applying the first message's action: the
    second message in the same batch is never processed."""

    async def _body() -> None:
        stop_event = asyncio.Event()
        applier = _StoppingApplier(stop_event)
        source = _TwoMessageSource([_message("first"), _message("second")])
        rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="tag", mailbox="X"))]

        with StateDB(tmp_path / "state.sqlite3") as state_db:
            await _run_message_loop(
                source=source,
                rules_state=RulesState(rules=rules),
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
                idle_delay_seconds=0.01,
            )

        assert applier.applied == ["first"]

    asyncio.run(_body())


def test_run_message_loop_sleeps_rather_than_busy_looping_on_an_empty_source(
    tmp_path: Path,
) -> None:
    """An always-empty source with a short idle_delay_seconds: over a
    fixed wall-clock window, poll() is called a bounded number of
    times — proving asyncio.sleep() is actually happening between
    calls, not a tight spin."""

    async def _body() -> None:
        stop_event = asyncio.Event()
        source = _CountingEmptySource()

        async def _stop_after(seconds: float) -> None:
            await asyncio.sleep(seconds)
            stop_event.set()

        with StateDB(tmp_path / "state.sqlite3") as state_db:
            await asyncio.gather(
                _run_message_loop(
                    source=source,
                    rules_state=RulesState(rules=[]),
                    default_unmatched_action=Action(type="escalate"),
                    executor=ActionExecutor(_StoppingApplier(asyncio.Event())),
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
                    idle_delay_seconds=0.05,
                ),
                _stop_after(0.22),
            )

        # ~0.22s / 0.05s idle delay ≈ 4-5 calls expected; a busy loop
        # would produce many thousands in the same window.
        assert source.calls <= 10

    start = time.monotonic()
    asyncio.run(_body())
    elapsed = time.monotonic() - start
    assert elapsed >= 0.2  # confirms the sleeps actually elapsed real time


def test_run_message_loop_drains_pending_control_plane_events(tmp_path: Path) -> None:
    """docs/DESIGN.md §6.2.2/§7.4 (M7): a pre-queued PendingAuditEvent
    is written via state_db.write_control_plane_audit_entry() on the
    very first iteration, and cleared from the pending list — proven
    directly against _run_message_loop(), the one code path that's
    allowed to touch state_db at all."""
    from spork.daemon.state import PendingAuditEvent

    async def _body(daemon_state: DaemonState) -> None:
        stop_event = asyncio.Event()
        source = _CountingEmptySource()

        async def _stop_after(seconds: float) -> None:
            await asyncio.sleep(seconds)
            stop_event.set()

        with StateDB(tmp_path / "state.sqlite3") as state_db:
            await asyncio.gather(
                _run_message_loop(
                    source=source,
                    rules_state=RulesState(rules=[]),
                    default_unmatched_action=Action(type="escalate"),
                    executor=ActionExecutor(_StoppingApplier(asyncio.Event())),
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
                    now=lambda: "2026-08-14T00:00:00Z",
                ),
                _stop_after(0.1),
            )

    state = DaemonState()
    state.pending_control_plane_events.append(
        PendingAuditEvent(event="daemon_paused", detail_json=None)
    )
    asyncio.run(_body(state))

    with StateDB(tmp_path / "state.sqlite3") as db:
        entries = db.get_audit_entries()

    assert state.pending_control_plane_events == []
    assert any(e.event == "daemon_paused" and e.jmap_id == "" for e in entries)


def test_run_message_loop_drains_pending_events_even_while_paused(tmp_path: Path) -> None:
    """A pending event still gets written on the very next iteration
    even when daemon_state.paused is True — otherwise a second
    "pause" while already paused (or a "resume" that hasn't been
    observed by the loop yet) would never get its own audit entry
    written until some later unrelated resume."""
    from spork.daemon.state import PendingAuditEvent

    async def _body(daemon_state: DaemonState) -> None:
        stop_event = asyncio.Event()
        source = _CountingEmptySource()

        async def _stop_after(seconds: float) -> None:
            await asyncio.sleep(seconds)
            stop_event.set()

        with StateDB(tmp_path / "state.sqlite3") as state_db:
            await asyncio.gather(
                _run_message_loop(
                    source=source,
                    rules_state=RulesState(rules=[]),
                    default_unmatched_action=Action(type="escalate"),
                    executor=ActionExecutor(_StoppingApplier(asyncio.Event())),
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
                    now=lambda: "2026-08-14T00:00:00Z",
                ),
                _stop_after(0.1),
            )

    state = DaemonState(paused=True)
    state.pending_control_plane_events.append(
        PendingAuditEvent(event="daemon_paused", detail_json=None)
    )
    asyncio.run(_body(state))

    with StateDB(tmp_path / "state.sqlite3") as db:
        entries = db.get_audit_entries()

    assert state.pending_control_plane_events == []
    assert any(e.event == "daemon_paused" and e.jmap_id == "" for e in entries)


def test_run_daemon_propagates_a_missing_rules_file_error(tmp_path: Path) -> None:
    """A rules_path that doesn't exist is a clear RulesLoadError,
    propagated as-is — run_daemon() is a library function, not a CLI
    command, so it doesn't catch/report this itself (main.py does)."""
    config = _minimal_config(tmp_path, rules_path=tmp_path / "does-not-exist.toml")

    async def _body() -> None:
        with pytest.raises(RulesLoadError):
            await run_daemon(config, idle_delay_seconds=0.01)

    asyncio.run(_body())


def test_run_daemon_propagates_an_unrecorded_tier2_response_error(tmp_path: Path) -> None:
    """A message escalates, but RecordedLLMClient has no recorded
    response for its subject — UnrecordedResponseError propagates (as
    asyncio.TaskGroup's ExceptionGroup) rather than being swallowed,
    same fail-loud posture as the missing-rules-file case above: a
    raise here means the message is retried next cycle (docs/DESIGN.md
    §10.7), not silently marked processed with no real outcome."""
    messages_path = tmp_path / "messages.json"
    messages_path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "No recorded response for this",
                    "body_text": "b",
                }
            ]
        )
    )
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
        [[rule]]
        id = "always-escalate"
        when = { always = true }
        action = { type = "escalate" }
        """
    )
    responses_path = tmp_path / "responses.json"
    responses_path.write_text("{}")  # nothing recorded

    config = SporkConfig(
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

    async def _body() -> None:
        with pytest.raises(ExceptionGroup) as exc_info:
            await run_daemon(config, idle_delay_seconds=0.01)
        assert any(isinstance(exc, UnrecordedResponseError) for exc in exc_info.value.exceptions)

    asyncio.run(_body())


class _RecordingAlerter:
    """A real `Alerter` (structurally) that records every `notify()`
    call instead of delivering anywhere — precise enough to count
    exact firings, unlike scraping LoggingAlerter's log output."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, AlertUrgency]] = []

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        self.calls.append((title, body, urgency))


def test_check_daily_budget_alert_fires_once_and_stamps_todays_date(tmp_path: Path) -> None:
    """Budget already exhausted (1 call recorded against a budget of
    1): the first check fires and stamps the date; a second check the
    same day is a no-op (docs/DESIGN.md §12.3's one-shot-per-day rule)."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.record_llm_call("2026-01-01", tokens_in=1, tokens_out=1)
        daemon_state = DaemonState()
        alerter = _RecordingAlerter()
        ops = PipelineObserver(alerter)
        tiering = TieringConfig(daily_call_budget=1)

        _check_daily_budget_alert(
            daemon_state=daemon_state,
            state_db=db,
            tiering=tiering,
            ops=ops,
            now=lambda: "2026-01-01T00:00:00+00:00",
        )
        assert daemon_state.budget_exhausted_alert_date == "2026-01-01"
        assert len(alerter.calls) == 1

        _check_daily_budget_alert(
            daemon_state=daemon_state,
            state_db=db,
            tiering=tiering,
            ops=ops,
            now=lambda: "2026-01-01T23:59:00+00:00",
        )
        assert len(alerter.calls) == 1  # unchanged: already alerted today


def test_check_daily_budget_alert_does_nothing_one_call_below_the_limit(tmp_path: Path) -> None:
    """`has_budget_remaining()`'s limit is exclusive (§10.4) — one call
    short of the budget is still "remaining", not exhausted."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.record_llm_call("2026-01-01", tokens_in=1, tokens_out=1)
        daemon_state = DaemonState()
        alerter = _RecordingAlerter()
        ops = PipelineObserver(alerter)
        tiering = TieringConfig(daily_call_budget=2)

        _check_daily_budget_alert(
            daemon_state=daemon_state,
            state_db=db,
            tiering=tiering,
            ops=ops,
            now=lambda: "2026-01-01T00:00:00+00:00",
        )

        assert daemon_state.budget_exhausted_alert_date is None
        assert alerter.calls == []


def test_check_daily_budget_alert_fires_again_after_a_date_rollover(tmp_path: Path) -> None:
    """The guard is a date-equality check, not a boolean flag — once
    `now()` reports a new day, an exhausted budget alerts again with
    no explicit reset step anywhere (docs/DESIGN.md §12.3)."""
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.record_llm_call("2026-01-01", tokens_in=1, tokens_out=1)
        db.record_llm_call("2026-01-02", tokens_in=1, tokens_out=1)
        daemon_state = DaemonState()
        alerter = _RecordingAlerter()
        ops = PipelineObserver(alerter)
        tiering = TieringConfig(daily_call_budget=1)

        _check_daily_budget_alert(
            daemon_state=daemon_state,
            state_db=db,
            tiering=tiering,
            ops=ops,
            now=lambda: "2026-01-01T00:00:00+00:00",
        )
        _check_daily_budget_alert(
            daemon_state=daemon_state,
            state_db=db,
            tiering=tiering,
            ops=ops,
            now=lambda: "2026-01-02T00:00:00+00:00",
        )

        assert daemon_state.budget_exhausted_alert_date == "2026-01-02"
        assert len(alerter.calls) == 2
