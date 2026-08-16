"""`spork backfill` (docs/ROADMAP.md M8, docs/DESIGN.md §9.3).

Retroactively categorizes existing mail — deliberately not part of
`sporkd`'s steady-state loop, which never replays history
(`fetch_new_messages(since_cursor=None)` baselines and discards it by
design, M1). Standalone like `reclassify`/`logs`: opens its own
`Provider`/`StateDB` directly, works whether or not `sporkd` is
running. Reuses `process_message()`/`escalate_message()` exactly as
`reclassify` does, over a `BackfillProvider` page at a time instead of
one message-id — the same Tier 1/Tier 2 pipeline live ingestion uses,
per M8's exit criteria.
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
from spork.core.providers.base import BackfillProvider
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

# Same "one catchable tuple per command" convention as reclassify.py.
_LoadError = (
    ProviderLoadError,
    RulesLoadError,
    UnknownClassifierError,
    AlerterLoadError,
    LLMClientLoadError,
    SecretsError,
)


class BackfillNotSupportedError(Exception):
    """Raised when the configured provider has no BackfillProvider capability.

    A clean, named error rather than an AttributeError the first time
    something tries to call query_messages() on a provider that never
    promised it — same "report not applicable, don't crash" treatment
    `spork doctor` gives a non-JMAP provider's connectivity check."""


def backfill(
    unread_only: bool = typer.Option(False, "--unread-only", help="Only page through unread mail."),
    limit: int = typer.Option(  # noqa: B008 - idiomatic Typer, not a mutable default
        50,
        "--limit",
        help=(
            "Maximum number of messages to process this run. Deliberately "
            "conservative by default (docs/ROADMAP.md M8): a several-"
            "thousand-message Inbox must never be swept unbounded by "
            "accident — raise explicitly for a larger run."
        ),
    ),
    page_size: int = typer.Option(50, "--page-size", help="Messages fetched per Email/query page."),
) -> None:
    """Retroactively categorize existing mail through the same Tier 1/Tier 2
    pipeline live ingestion uses (docs/ROADMAP.md M8)."""
    try:
        config = load_config()
    except ConfigLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        _backfill(config, unread_only=unread_only, limit=limit, page_size=page_size)
    except (*_LoadError, BackfillNotSupportedError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _backfill(config: SporkConfig, *, unread_only: bool, limit: int, page_size: int) -> None:
    secrets = resolve_runtime_secrets(config, reason="backfill")
    provider = build_provider(config, secrets)
    if not isinstance(provider, BackfillProvider):
        raise BackfillNotSupportedError(
            f"provider {config.provider.spec!r} does not support backfill "
            "(no query_messages() capability)"
        )

    executor = ActionExecutor(provider.build_action_applier())
    ops = PipelineObserver(build_alerter(config, secrets))
    rules = load_rules(config.rules_path)
    classifier: TextClassifier | None = (
        classify_registry.get(config.tiering.local_classifier)
        if config.tiering.local_classifier is not None
        else None
    )
    default_unmatched_action = Action(type=config.tiering.default_unmatched_action)
    llm_client = build_llm_client(config, secrets)

    processed = 0
    tier1_actions = 0
    tier2_verdicts = 0
    budget_exhausted = False
    position = 0

    with StateDB(config.db_path) as state_db:
        # Distinct from process_message()'s/escalate_message()'s own
        # per-message outcome rows below (docs/DESIGN.md §7.4, M7) — a
        # backfill run stays visible in the audit trail as one
        # operator-triggered event, same pattern as
        # reclassify_triggered.
        state_db.write_control_plane_audit_entry(
            ts=datetime.now(UTC).isoformat(),
            event="backfill_triggered",
            detail_json=json.dumps(
                {"unread_only": unread_only, "limit": limit, "page_size": page_size}
            ),
        )

        while processed < limit and not budget_exhausted:
            page = provider.query_messages(
                unread_only=unread_only, position=position, limit=min(page_size, limit - processed)
            )
            if not page.messages:
                break

            for message in page.messages:
                if processed >= limit:
                    break
                # process_message()'s own idempotency gate (docs/DESIGN.md
                # §11) is what actually satisfies M8's "never reprocess a
                # message the live path already claimed" exit criterion —
                # a message process_message() (or a prior backfill run)
                # already marked processed comes back as verdict=None here,
                # not reprocessed, not re-acted-on.
                verdict = process_message(
                    message,
                    rules,
                    default_unmatched_action=default_unmatched_action,
                    executor=executor,
                    state_db=state_db,
                    ops=ops,
                    classifier=classifier,
                )
                processed += 1
                if verdict is None:
                    continue
                tier1_actions += 1
                if verdict.action.type == "escalate":
                    tier2_verdict = escalate_message(
                        message,
                        thread_history_reader=provider.build_thread_history_reader(),
                        mailbox_lister=provider.build_mailbox_lister(),
                        llm_client=llm_client,
                        executor=executor,
                        draft_creator=provider.build_draft_creator(),
                        state_db=state_db,
                        ops=ops,
                        tiering=config.tiering,
                    )
                    if tier2_verdict is None:
                        budget_exhausted = True
                        break
                    tier2_verdicts += 1

            position += len(page.messages)
            if not page.has_more:
                break

    typer.echo(
        f"backfill: processed {processed} messages "
        f"({tier1_actions} Tier 1 actions, {tier2_verdicts} Tier 2 verdicts)"
    )
    if budget_exhausted:
        typer.echo("backfill: stopped early - Tier 2's daily call budget is exhausted", err=True)
