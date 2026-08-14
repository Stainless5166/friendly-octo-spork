"""run_daemon(): the asyncio daemon loop, composed (docs/DESIGN.md §6.2.1/§6.2.2).

Bridges every synchronous piece this daemon has (`Source.poll()`, the
entire `process_message()` call, and — when Tier 1 escalates —
`process_tier2_message()`, each of which may itself block on a live
network call) into the asyncio loop via `asyncio.to_thread()`. Runs
the message loop and the IPC control socket as two tasks in one
`asyncio.TaskGroup()`, sharing `DaemonState` (§6.2.2).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spork.core.actions.executor import ActionExecutor
from spork.core.classify import registry as classify_registry
from spork.core.classify.base import TextClassifier
from spork.core.config.paths import resolve_socket_path
from spork.core.config.schema import SporkConfig, TieringConfig
from spork.core.ipc.server import IpcServer
from spork.core.llm.base import LLMClient
from spork.core.llm.budget import has_budget_remaining
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2.escalate import escalate_message
from spork.core.providers.base import DraftCreator, MailboxLister, ThreadHistoryReader
from spork.core.rules.loader import load_rules
from spork.core.rules.schema import Action
from spork.core.runtime import (
    build_alerter,
    build_llm_client,
    build_provider,
    resolve_runtime_secrets,
)
from spork.core.secrets import Secrets
from spork.core.sources.base import Source
from spork.core.state.db import StateDB
from spork.core.systemd.notify import notify
from spork.daemon.state import DaemonState, PendingAuditEvent, RulesState


def _utc_now_iso() -> str:
    """Default `now` for `_run_message_loop()`'s budget-alert check —
    same shape as every other `now: Callable[[], str]` DI default in
    this codebase (`spork.core.pipeline.default`/`tier2.default`)."""
    return datetime.now(UTC).isoformat()


async def run_daemon(
    config: SporkConfig,
    *,
    stop_event: asyncio.Event | None = None,
    daemon_state: DaemonState | None = None,
    idle_delay_seconds: float = 1.0,
    notify_fn: Callable[[str], bool] = notify,
    secrets: Secrets | None = None,
) -> None:
    """Compose `config` into a running Tier 1+2 daemon loop + IPC server.

    Runs until `stop_event` is set (a fresh one is created if none is
    given, so a caller with no shutdown mechanism yet — `main.py`
    before it wires up signal handlers, e.g. — still gets a valid,
    if-never-externally-stoppable, loop). `daemon_state`/
    `idle_delay_seconds`/`notify_fn` are injectable the same way `now`/
    `new_correlation_id` are elsewhere in this codebase — production
    callers never override them; tests use a fresh `DaemonState`/small
    delay/stub notify function to control and speed up what they
    exercise.
    """
    stop_event = stop_event if stop_event is not None else asyncio.Event()
    daemon_state = daemon_state if daemon_state is not None else DaemonState()
    daemon_state.started_at = datetime.now(UTC).isoformat()

    runtime_secrets = (
        secrets
        if secrets is not None
        else resolve_runtime_secrets(config, reason="start sporkd")
    )
    provider = build_provider(config, runtime_secrets)
    source = provider.build_source()
    executor = ActionExecutor(provider.build_action_applier())
    draft_creator = provider.build_draft_creator()
    thread_history_reader = provider.build_thread_history_reader()
    mailbox_lister = provider.build_mailbox_lister()

    # Loaded before llm/alerts (unchanged relative order from before
    # Tier 2 was wired in) — test_run_daemon_propagates_a_missing_rules_file_error
    # relies on a bad rules_path surfacing as RulesLoadError regardless
    # of what else in config is or isn't configured.
    rules_state = RulesState(rules=load_rules(config.rules_path))

    llm_client = build_llm_client(config, runtime_secrets)

    alerter = build_alerter(config, runtime_secrets)
    ops = PipelineObserver(alerter)

    classifier: TextClassifier | None = (
        classify_registry.get(config.tiering.local_classifier)
        if config.tiering.local_classifier is not None
        else None
    )
    default_unmatched_action = Action(type=config.tiering.default_unmatched_action)

    # config.socket_path is Optional on SporkConfig — load_config()
    # always resolves it before returning (§7.2), but run_daemon() can
    # also be called directly with a hand-built SporkConfig (tests do
    # this), so it's resolved defensively here too rather than trusting
    # every caller went through load_config() first.
    socket_path = config.socket_path if config.socket_path is not None else resolve_socket_path()
    ipc_server = IpcServer(
        socket_path, handlers=_build_ipc_handlers(daemon_state, rules_state, config.rules_path)
    )

    # Everything above can fail loudly (a bad provider/rules/llm/alerts
    # spec); only once composition has actually succeeded is this
    # process "ready" in any meaningful sense — docs/DESIGN.md §14.
    # A safe no-op outside a Type=notify unit (every test, every plain
    # `uv run sporkd`): notify()/notify_fn never raises.
    notify_fn("READY=1")

    with StateDB(config.db_path) as state_db:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                _run_message_loop(
                    source=source,
                    rules_state=rules_state,
                    default_unmatched_action=default_unmatched_action,
                    executor=executor,
                    state_db=state_db,
                    ops=ops,
                    classifier=classifier,
                    llm_client=llm_client,
                    draft_creator=draft_creator,
                    thread_history_reader=thread_history_reader,
                    mailbox_lister=mailbox_lister,
                    tiering=config.tiering,
                    daemon_state=daemon_state,
                    stop_event=stop_event,
                    idle_delay_seconds=idle_delay_seconds,
                )
            )
            tg.create_task(ipc_server.serve(stop_event))


def _build_ipc_handlers(
    daemon_state: DaemonState,
    rules_state: RulesState,
    rules_path: Path,
) -> dict[str, Any]:
    """The status/pause/resume/reload handlers `IpcServer` dispatches to.

    status/pause/resume deliberately touch only `DaemonState` — never
    `StateDB` — since these run as coroutines on the event-loop thread
    and could otherwise race a `to_thread(process_message, ...)` call
    touching the same connection from a worker thread (docs/DESIGN.md
    §6.2.2). pause/resume's control-plane audit entries (M7, §7.4)
    respect this too: they queue a `PendingAuditEvent` onto
    `DaemonState` (an in-memory append, no different in kind from
    flipping `.paused`) rather than writing to `StateDB` directly —
    `_run_message_loop()` is what actually drains and writes them.
    `reload` touches `RulesState` the same safe way: it
    reassigns `.rules` wholesale rather than mutating the existing list
    in place (§6.2.2/§7.5) — a re-`load_rules()` failure is caught here
    and reported as `IpcResponse(ok=False, ...)`, leaving `rules_state.rules`
    at its last-known-good value instead of taking the daemon down.
    """

    def _status(params: dict[str, Any]) -> dict[str, Any]:
        return {"paused": daemon_state.paused, "started_at": daemon_state.started_at}

    def _pause(params: dict[str, Any]) -> dict[str, Any]:
        daemon_state.paused = True
        daemon_state.pending_control_plane_events.append(
            PendingAuditEvent(event="daemon_paused", detail_json=None)
        )
        return {"paused": True}

    def _resume(params: dict[str, Any]) -> dict[str, Any]:
        daemon_state.paused = False
        daemon_state.pending_control_plane_events.append(
            PendingAuditEvent(event="daemon_resumed", detail_json=None)
        )
        return {"paused": False}

    def _reload(params: dict[str, Any]) -> dict[str, Any]:
        # RulesLoadError (a bad hand-edit) propagates to IpcServer's own
        # generic handler-exception catch, which turns it into
        # IpcResponse(ok=False, error=str(exc)) — rules_state.rules is
        # only reassigned below, so a failed reload never touches it.
        new_rules = load_rules(rules_path)
        rules_state.rules = new_rules
        return {"rule_count": len(new_rules)}

    return {"status": _status, "pause": _pause, "resume": _resume, "reload": _reload}


def _check_daily_budget_alert(
    *,
    daemon_state: DaemonState,
    state_db: StateDB,
    tiering: TieringConfig,
    ops: PipelineObserver,
    now: Callable[[], str],
    new_correlation_id: Callable[[], str] = lambda: uuid.uuid4().hex,
) -> None:
    """One-shot daemon-health alert when today's daily LLM call budget
    is exhausted (docs/DESIGN.md §12.3).

    Distinct from `RecordBudgetExhaustedFilter`'s existing per-message
    "Tier 2 skipped" alert: that one fires every time an escalation
    lands on an already-exhausted budget, by design (§10's never-drop
    policy). This one is a daemon-lifecycle signal — "sporkd itself
    has hit its ceiling for today" — meant to fire at most once per
    calendar day. The guard is a date-equality check against
    `daemon_state.budget_exhausted_alert_date`, not a boolean flag, so
    the alert self-resets the moment `now()` reports a new day, with
    no midnight timer or explicit reset logic anywhere.
    """
    today = now()[:10]
    if daemon_state.budget_exhausted_alert_date == today:
        return
    usage = state_db.get_llm_usage(today)
    if has_budget_remaining(usage, daily_call_budget=tiering.daily_call_budget):
        return
    daemon_state.budget_exhausted_alert_date = today
    ops.alert(
        new_correlation_id(),
        "Daily LLM budget exhausted",
        f"sporkd has used {usage.calls}/{tiering.daily_call_budget} Tier 2 calls today; "
        "further escalations are being skipped until the budget resets.",
        urgency="critical",
    )


async def _run_message_loop(
    *,
    source: Source,
    rules_state: RulesState,
    default_unmatched_action: Action,
    executor: ActionExecutor,
    state_db: StateDB,
    ops: PipelineObserver,
    classifier: TextClassifier | None,
    llm_client: LLMClient,
    draft_creator: DraftCreator,
    thread_history_reader: ThreadHistoryReader,
    mailbox_lister: MailboxLister,
    tiering: TieringConfig,
    daemon_state: DaemonState,
    stop_event: asyncio.Event,
    idle_delay_seconds: float,
    now: Callable[[], str] = _utc_now_iso,
) -> None:
    """Repeatedly poll `source` and run each message through Tier 1,
    escalating to Tier 2 in the same cycle when Tier 1 routes
    "escalate", until `stop_event` is set.

    `source.poll()` already blocks until it has something (§9.2's
    Trigger/ContentFetcher contract) — jmapc offers no async
    alternative to bridge against (confirmed, not assumed: it's
    `requests` + a blocking `sseclient` generator under the hood), so
    each call runs via `asyncio.to_thread()` rather than a persistent
    listener thread + hand-off queue; the default thread pool recycles
    a worker between calls since nothing here runs concurrently with
    itself. An empty batch (a caught-up source, or one like
    `FileProvider`'s that settles to `[]` forever once exhausted) gets
    a real, cancellable `asyncio.sleep()` rather than spinning a CPU
    core. Shutdown latency is bounded by whatever `poll()` call is
    currently in flight — cancelling a `to_thread` task doesn't kill
    the underlying OS thread (§6.2.1). While `daemon_state.paused`,
    `poll()` isn't called at all (§6.2.2's honest caveat: this also
    stops fetching, not just acting on what's already fetched).
    `rules_state.rules` is read fresh right after each `poll()` call
    (not captured once at loop start), so a `reload` IPC command
    (§6.2.2/§7.5) takes effect for the very next batch, not just a
    future daemon restart. After each escalation, `daemon_state` is
    checked for a one-shot daily-budget-exhausted daemon-health alert
    (§12.3) — distinct from `RecordBudgetExhaustedFilter`'s existing
    per-message alert, which fires every time regardless. `now` is
    injectable the same way it is on `process_message()`/
    `process_tier2_message()`: production callers never override it,
    tests use it to control which day's budget row the check reads.
    """
    while not stop_event.is_set():
        # Drained unconditionally, even while paused (docs/DESIGN.md
        # §6.2.2/§7.4, M7) — a repeated pause, or a resume this
        # iteration hasn't observed yet, still gets its own audit
        # entry written rather than waiting for some later unrelated
        # state change. Reassigning to a fresh list (not .clear())
        # before the loop below means a pause/resume call arriving
        # mid-drain appends to the *new* list, never the one already
        # being iterated (the same swap-the-reference safety pattern
        # RulesState.rules reassignment already uses).
        if daemon_state.pending_control_plane_events:
            pending = daemon_state.pending_control_plane_events
            daemon_state.pending_control_plane_events = []
            for pending_event in pending:
                await asyncio.to_thread(
                    state_db.write_control_plane_audit_entry,
                    ts=now(),
                    event=pending_event.event,
                    detail_json=pending_event.detail_json,
                )

        if daemon_state.paused:
            await asyncio.sleep(idle_delay_seconds)
            continue
        messages = await asyncio.to_thread(source.poll)
        rules = rules_state.rules
        if not messages:
            await asyncio.sleep(idle_delay_seconds)
            continue
        for message in messages:
            if stop_event.is_set():
                return
            verdict = await asyncio.to_thread(
                process_message,
                message,
                rules,
                default_unmatched_action=default_unmatched_action,
                executor=executor,
                state_db=state_db,
                ops=ops,
                classifier=classifier,
            )
            # A second, separate to_thread call, strictly sequential
            # with the one above — StateDB's sequential-access
            # condition (§6.2.1) only needs "never concurrent", not
            # "one to_thread wrapper per message" (docs/DESIGN.md). The
            # whole thing (thread-history/mailbox-list reads included)
            # runs inside one worker-thread call via escalate_message()
            # (spork.core.pipeline.tier2.escalate, M5) — those reads
            # may themselves be real I/O against a live backend, so
            # they belong off the event-loop thread too, not called
            # directly from this coroutine.
            if verdict is not None and verdict.action.type == "escalate":
                await asyncio.to_thread(
                    escalate_message,
                    message,
                    thread_history_reader=thread_history_reader,
                    mailbox_lister=mailbox_lister,
                    llm_client=llm_client,
                    executor=executor,
                    draft_creator=draft_creator,
                    state_db=state_db,
                    ops=ops,
                    tiering=tiering,
                )
                _check_daily_budget_alert(
                    daemon_state=daemon_state,
                    state_db=state_db,
                    tiering=tiering,
                    ops=ops,
                    now=now,
                )
