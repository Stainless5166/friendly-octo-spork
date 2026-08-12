"""run_daemon(): the asyncio daemon loop, composed (docs/DESIGN.md §6.2.1).

Bridges every synchronous piece this daemon has (`Source.poll()`, and
the entire `process_message()` call — which may itself block on a live
`ActionApplier`'s network write) into the asyncio loop via
`asyncio.to_thread()`. Tier 1 only — see §6.2.1 for why chaining a
freshly-escalated message into Tier 2 needs a `Provider` capability
this round doesn't have yet.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.loader import load_alerter
from spork.core.classify import registry as classify_registry
from spork.core.classify.base import TextClassifier
from spork.core.config.schema import SporkConfig
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.providers.loader import load_provider
from spork.core.rules.loader import load_rules
from spork.core.rules.schema import Action, Rule
from spork.core.sources.base import Source
from spork.core.state.db import StateDB


async def run_daemon(
    config: SporkConfig,
    *,
    stop_event: asyncio.Event | None = None,
    idle_delay_seconds: float = 1.0,
) -> None:
    """Compose `config` into a running Tier 1 daemon loop.

    Runs until `stop_event` is set (a fresh one is created if none is
    given, so a caller with no shutdown mechanism yet — `main.py`
    before it wires up signal handlers, e.g. — still gets a valid,
    if-never-externally-stoppable, loop). `idle_delay_seconds` is
    injectable the same way `now`/`new_correlation_id` are elsewhere
    in this codebase — production callers never override it; tests use
    a small value to stay fast.
    """
    stop_event = stop_event if stop_event is not None else asyncio.Event()

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

    with StateDB(config.db_path) as state_db:
        await _run_message_loop(
            source=source,
            rules=rules,
            default_unmatched_action=default_unmatched_action,
            executor=executor,
            state_db=state_db,
            ops=ops,
            classifier=classifier,
            stop_event=stop_event,
            idle_delay_seconds=idle_delay_seconds,
        )


async def _run_message_loop(
    *,
    source: Source,
    rules: Sequence[Rule],
    default_unmatched_action: Action,
    executor: ActionExecutor,
    state_db: StateDB,
    ops: PipelineObserver,
    classifier: TextClassifier | None,
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
    the underlying OS thread (§6.2.1).
    """
    while not stop_event.is_set():
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
