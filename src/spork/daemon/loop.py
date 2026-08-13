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
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.loader import load_alerter
from spork.core.classify import registry as classify_registry
from spork.core.classify.base import TextClassifier
from spork.core.config.paths import resolve_socket_path
from spork.core.config.schema import SporkConfig, TieringConfig
from spork.core.ipc.server import IpcServer
from spork.core.llm.base import LLMClient
from spork.core.llm.loader import load_llm_client
from spork.core.models import NormalizedMessage
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2 import process_tier2_message
from spork.core.providers.base import DraftCreator, MailboxLister, ThreadHistoryReader
from spork.core.providers.loader import load_provider
from spork.core.rules.loader import load_rules
from spork.core.rules.schema import Action
from spork.core.sources.base import Source
from spork.core.state.db import StateDB
from spork.daemon.state import DaemonState, RulesState


async def run_daemon(
    config: SporkConfig,
    *,
    stop_event: asyncio.Event | None = None,
    daemon_state: DaemonState | None = None,
    idle_delay_seconds: float = 1.0,
) -> None:
    """Compose `config` into a running Tier 1+2 daemon loop + IPC server.

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
    draft_creator = provider.build_draft_creator()
    thread_history_reader = provider.build_thread_history_reader()
    mailbox_lister = provider.build_mailbox_lister()

    # Loaded before llm/alerts (unchanged relative order from before
    # Tier 2 was wired in) — test_run_daemon_propagates_a_missing_rules_file_error
    # relies on a bad rules_path surfacing as RulesLoadError regardless
    # of what else in config is or isn't configured.
    rules_state = RulesState(rules=load_rules(config.rules_path))

    llm_client = load_llm_client(config.llm.spec, **config.llm.kwargs)

    alerter = load_alerter(config.alerts.spec, **config.alerts.kwargs)
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
    §6.2.2). `reload` touches `RulesState` the same safe way: it
    reassigns `.rules` wholesale rather than mutating the existing list
    in place (§6.2.2/§7.5) — a re-`load_rules()` failure is caught here
    and reported as `IpcResponse(ok=False, ...)`, leaving `rules_state.rules`
    at its last-known-good value instead of taking the daemon down.
    """

    def _status(params: dict[str, Any]) -> dict[str, Any]:
        return {"paused": daemon_state.paused, "started_at": daemon_state.started_at}

    def _pause(params: dict[str, Any]) -> dict[str, Any]:
        daemon_state.paused = True
        return {"paused": True}

    def _resume(params: dict[str, Any]) -> dict[str, Any]:
        daemon_state.paused = False
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
    future daemon restart.
    """
    while not stop_event.is_set():
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
            # runs inside one worker-thread call via _escalate_to_tier2
            # — those reads may themselves be real I/O against a live
            # backend, so they belong off the event-loop thread too,
            # not called directly from this coroutine.
            if verdict is not None and verdict.action.type == "escalate":
                await asyncio.to_thread(
                    _escalate_to_tier2,
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


def _escalate_to_tier2(
    message: NormalizedMessage,
    *,
    thread_history_reader: ThreadHistoryReader,
    mailbox_lister: MailboxLister,
    llm_client: LLMClient,
    executor: ActionExecutor,
    draft_creator: DraftCreator,
    state_db: StateDB,
    ops: PipelineObserver,
    tiering: TieringConfig,
) -> None:
    """Resolves the two Provider-supplied reads Tier 2 needs and runs
    `process_tier2_message()` — synchronous end to end so the whole
    thing is one `asyncio.to_thread()` call (see the caller above).
    """
    context = thread_history_reader.get_thread_context(message)
    process_tier2_message(
        message,
        to_addresses=_parse_to_addresses(message),
        thread_prior_subject=context.prior_subject,
        thread_user_has_replied=context.user_has_replied,
        available_mailboxes=mailbox_lister.list_mailboxes(),
        llm_client=llm_client,
        executor=executor,
        draft_creator=draft_creator,
        state_db=state_db,
        ops=ops,
        allowed_categories=tiering.allowed_categories,
        daily_call_budget=tiering.daily_call_budget,
        alert_threshold=tiering.alert_threshold,
        autoact_threshold=tiering.autoact_threshold,
        max_body_chars=tiering.max_body_chars,
    )


def _parse_to_addresses(message: NormalizedMessage) -> Sequence[str]:
    """Real `to_addresses`, parsed from `NormalizedMessage.headers["To"]`
    (docs/DESIGN.md §6.2.1) — comma-split, whitespace-stripped, empty
    entries dropped. `()` when there's no `To:` header at all, never a
    fabricated address.
    """
    to_header = message.headers.get("To", "")
    return tuple(addr.strip() for addr in to_header.split(",") if addr.strip())
