"""run_daemon(): the asyncio daemon loop, composed (docs/DESIGN.md §6.2.1/§6.2.2).

Bridges every synchronous piece this daemon has (`Source.poll()`, and
the entire `process_message()` call — which may itself block on a live
`ActionApplier`'s network write) into the asyncio loop via
`asyncio.to_thread()`. Tier 1 only — see §6.2.1 for why chaining a
freshly-escalated message into Tier 2 needs a `Provider` capability
this round doesn't have yet. Runs the message loop and the IPC control
socket as two tasks in one `asyncio.TaskGroup()`, sharing `DaemonState`
(§6.2.2).
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.loader import load_alerter
from spork.core.classify import registry as classify_registry
from spork.core.classify.base import TextClassifier
from spork.core.config.paths import resolve_socket_path
from spork.core.config.schema import SporkConfig
from spork.core.ipc.server import IpcServer
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.providers.loader import load_provider
from spork.core.rules.loader import load_rules
from spork.core.rules.schema import Action, Rule
from spork.core.sources.base import Source
from spork.core.state.db import StateDB
from spork.daemon.state import DaemonState


async def run_daemon(
    config: SporkConfig,
    *,
    stop_event: asyncio.Event | None = None,
    daemon_state: DaemonState | None = None,
    idle_delay_seconds: float = 1.0,
) -> None:
    """Compose `config` into a running Tier 1 daemon loop + IPC server.

    Runs until `stop_event` is set (a fresh one is created if none is
    given, so a caller with no shutdown mechanism yet — `main.py`
    before it wires up signal handlers, e.g. — still gets a valid,
    if-never-externally-stoppable, loop). `daemon_state`/
    `idle_delay_seconds` are injectable the same way `now`/
    `new_correlation_id` are elsewhere in this codebase — production
    callers never override them; tests use a fresh `DaemonState`/small
    delay to control and speed up what they exercise.
    """
    stop_event = stop_event if stop_event is not None else asyncio.Event()
    daemon_state = daemon_state if daemon_state is not None else DaemonState()
    daemon_state.started_at = datetime.now(UTC).isoformat()

    provider = load_provider(config.provider.spec, **config.provider.kwargs)
    source = provider.build_source()
    executor = ActionExecutor(provider.build_action_applier())

    alerter = load_alerter(config.alerts.spec, **config.alerts.kwargs)
    ops = PipelineObserver(alerter)

    rules = load_rules(config.rules_path)
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
    ipc_server = IpcServer(socket_path, handlers=_build_ipc_handlers(daemon_state))

    with StateDB(config.db_path) as state_db:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                _run_message_loop(
                    source=source,
                    rules=rules,
                    default_unmatched_action=default_unmatched_action,
                    executor=executor,
                    state_db=state_db,
                    ops=ops,
                    classifier=classifier,
                    daemon_state=daemon_state,
                    stop_event=stop_event,
                    idle_delay_seconds=idle_delay_seconds,
                )
            )
            tg.create_task(ipc_server.serve(stop_event))


def _build_ipc_handlers(
    daemon_state: DaemonState,
) -> dict[str, Any]:
    """The status/pause/resume handlers `IpcServer` dispatches to.

    Deliberately touch only `DaemonState` — never `StateDB` — since
    these run as coroutines on the event-loop thread and could
    otherwise race a `to_thread(process_message, ...)` call touching
    the same connection from a worker thread (docs/DESIGN.md §6.2.2).
    """

    def _status(params: dict[str, Any]) -> dict[str, Any]:
        return {"paused": daemon_state.paused, "started_at": daemon_state.started_at}

    def _pause(params: dict[str, Any]) -> dict[str, Any]:
        daemon_state.paused = True
        return {"paused": True}

    def _resume(params: dict[str, Any]) -> dict[str, Any]:
        daemon_state.paused = False
        return {"paused": False}

    return {"status": _status, "pause": _pause, "resume": _resume}


async def _run_message_loop(
    *,
    source: Source,
    rules: Sequence[Rule],
    default_unmatched_action: Action,
    executor: ActionExecutor,
    state_db: StateDB,
    ops: PipelineObserver,
    classifier: TextClassifier | None,
    daemon_state: DaemonState,
    stop_event: asyncio.Event,
    idle_delay_seconds: float,
) -> None:
    """Repeatedly poll `source` and run each message through Tier 1,
    until `stop_event` is set.

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
    """
    while not stop_event.is_set():
        if daemon_state.paused:
            await asyncio.sleep(idle_delay_seconds)
            continue
        messages = await asyncio.to_thread(source.poll)
        if not messages:
            await asyncio.sleep(idle_delay_seconds)
            continue
        for message in messages:
            if stop_event.is_set():
                return
            await asyncio.to_thread(
                process_message,
                message,
                rules,
                default_unmatched_action=default_unmatched_action,
                executor=executor,
                state_db=state_db,
                ops=ops,
                classifier=classifier,
            )
