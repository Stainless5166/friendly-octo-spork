"""`spork reclassify <message-id>` (docs/DESIGN.md §7.4/§13).

Standalone, like `spork logs` — opens its own `Provider`/`StateDB`
directly and works whether or not `sporkd` is running, no new IPC
command needed. Safe by construction under SQLite's WAL mode (already
on, §7.4): a rare write collision with a running daemon is a bounded
retry (the default 5-second busy timeout), not a correctness risk.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import typer

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.loader import AlerterLoadError
from spork.core.classify import registry as classify_registry
from spork.core.classify.base import TextClassifier
from spork.core.classify.registry import UnknownClassifierError
from spork.core.config.loader import ConfigLoadError, load_config
from spork.core.config.schema import SporkConfig
from spork.core.llm.loader import LLMClientLoadError
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2.escalate import escalate_message
from spork.core.providers.base import MessageNotFoundError
from spork.core.providers.loader import ProviderLoadError
from spork.core.rules.loader import RulesLoadError, load_rules
from spork.core.rules.schema import Action
from spork.core.runtime import (
    build_alerter,
    build_llm_client,
    build_provider,
    resolve_runtime_secrets,
)
from spork.core.secrets import SecretsError
from spork.core.state.db import StateDB

# Every load-error type this command's own calls (load_provider(),
# load_rules(), classify_registry.get(), load_alerter(),
# load_llm_client()) can raise — one catchable tuple, same "clean CLI
# error, never a raw traceback" convention every command in this CLI
# follows (mirrors spork.daemon.main's tuple, minus ConfigLoadError,
# which is caught separately below since it can fail before any of
# these are even reachable).
_LoadError = (
    ProviderLoadError,
    RulesLoadError,
    UnknownClassifierError,
    AlerterLoadError,
    LLMClientLoadError,
    SecretsError,
)


def reclassify(
    message_id: str = typer.Argument(  # noqa: B008 - idiomatic Typer, not a mutable default
        ..., help="The jmap_id of the message to force back through the pipeline."
    ),
) -> None:
    """Force one message back through the pipeline, even if it's
    already been acted on (docs/DESIGN.md §11).

    Runs Tier 1 with the idempotency gate bypassed; if the message
    escalates, runs Tier 2 as well, in the same invocation.
    """
    try:
        config = load_config()
    except ConfigLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # Every load-error/lookup-error this command can raise after
    # config is in hand, caught in one place — same "clean CLI error,
    # never a raw traceback" convention every command in this CLI
    # follows, not just the config-load step.
    try:
        _reclassify(message_id, config)
    except (*_LoadError, MessageNotFoundError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _reclassify(message_id: str, config: SporkConfig) -> None:
    secrets = resolve_runtime_secrets(config, reason="reclassify message")
    provider = build_provider(config, secrets)
    message = provider.build_message_lookup().get_message(message_id)

    executor = ActionExecutor(provider.build_action_applier())
    ops = PipelineObserver(build_alerter(config, secrets))
    rules = load_rules(config.rules_path)
    classifier: TextClassifier | None = (
        classify_registry.get(config.tiering.local_classifier)
        if config.tiering.local_classifier is not None
        else None
    )
    default_unmatched_action = Action(type=config.tiering.default_unmatched_action)

    with StateDB(config.db_path) as state_db:
        # Distinct from process_message()'s/escalate_message()'s own
        # per-message outcome row below (docs/DESIGN.md §7.4, M7) — "an
        # operator forced this" stays visible even though the outcome
        # looks the same as an ordinary automatic run.
        state_db.write_control_plane_audit_entry(
            ts=datetime.now(UTC).isoformat(),
            event="reclassify_triggered",
            detail_json=json.dumps({"message_id": message_id}),
        )
        verdict = process_message(
            message,
            rules,
            default_unmatched_action=default_unmatched_action,
            executor=executor,
            state_db=state_db,
            ops=ops,
            classifier=classifier,
            force=True,
        )

        if verdict is None or verdict.action.type != "escalate":
            action_type = verdict.action.type if verdict is not None else "none"
            typer.echo(f"{message_id}: Tier 1 -> {action_type}")
            return

        tier2_verdict = escalate_message(
            message,
            thread_history_reader=provider.build_thread_history_reader(),
            mailbox_lister=provider.build_mailbox_lister(),
            llm_client=build_llm_client(config, secrets),
            executor=executor,
            draft_creator=provider.build_draft_creator(),
            state_db=state_db,
            ops=ops,
            tiering=config.tiering,
        )

    if tier2_verdict is None:
        typer.echo(f"{message_id}: escalated, but Tier 2's daily call budget is exhausted")
    else:
        typer.echo(f"{message_id}: escalated -> Tier 2 -> {tier2_verdict.suggested_action.type}")
