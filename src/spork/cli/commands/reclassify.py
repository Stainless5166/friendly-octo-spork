"""`spork reclassify <message-id>` (docs/DESIGN.md §7.4/§13).

Standalone, like `spork logs` — opens its own `Provider`/`StateDB`
directly and works whether or not `sporkd` is running, no new IPC
command needed. Safe by construction under SQLite's WAL mode (already
on, §7.4): a rare write collision with a running daemon is a bounded
retry (the default 5-second busy timeout), not a correctness risk.
"""

from __future__ import annotations

import typer

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.loader import load_alerter
from spork.core.classify import registry as classify_registry
from spork.core.classify.base import TextClassifier
from spork.core.config.loader import ConfigLoadError, load_config
from spork.core.llm.loader import load_llm_client
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2.escalate import escalate_message
from spork.core.providers.base import MessageNotFoundError
from spork.core.providers.loader import load_provider
from spork.core.rules.loader import load_rules
from spork.core.rules.schema import Action
from spork.core.state.db import StateDB


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

    provider = load_provider(config.provider.spec, **config.provider.kwargs)
    try:
        message = provider.build_message_lookup().get_message(message_id)
    except MessageNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    executor = ActionExecutor(provider.build_action_applier())
    ops = PipelineObserver(load_alerter(config.alerts.spec, **config.alerts.kwargs))
    rules = load_rules(config.rules_path)
    classifier: TextClassifier | None = (
        classify_registry.get(config.tiering.local_classifier)
        if config.tiering.local_classifier is not None
        else None
    )
    default_unmatched_action = Action(type=config.tiering.default_unmatched_action)

    with StateDB(config.db_path) as state_db:
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
            llm_client=load_llm_client(config.llm.spec, **config.llm.kwargs),
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
