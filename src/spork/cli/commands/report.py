"""Bounded, read-only message reporting for company-mail staging.

Unlike `backfill`, this command never constructs the LLM, alerter, action
executor, or StateDB. It evaluates a bounded sample with Tier 1 only and
emits aggregate metadata, so the report cannot mark messages or apply a
mailbox mutation as a side effect of inspection.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

import typer

from spork.core.classify import registry as classify_registry
from spork.core.classify.base import TextClassifier
from spork.core.classify.registry import UnknownClassifierError
from spork.core.config.loader import ConfigLoadError, load_config
from spork.core.config.schema import SporkConfig
from spork.core.providers.base import BackfillProvider
from spork.core.providers.loader import ProviderLoadError
from spork.core.rules.engine import evaluate
from spork.core.rules.loader import RulesLoadError, load_rules
from spork.core.rules.schema import Action
from spork.core.runtime import build_provider, resolve_runtime_secrets
from spork.core.secrets import SecretsError


class ReportNotSupportedError(Exception):
    """Raised when the configured provider cannot page existing messages."""


_ReportError = (
    ProviderLoadError,
    RulesLoadError,
    UnknownClassifierError,
    SecretsError,
    ReportNotSupportedError,
)


def report(
    limit: int = typer.Option(  # noqa: B008 - idiomatic Typer, not a mutable default
        50,
        "--limit",
        min=1,
        max=50,
        help="Maximum number of messages to inspect; capped at 50 for staging safety.",
    ),
    page_size: int = typer.Option(  # noqa: B008 - idiomatic Typer, not a mutable default
        50, "--page-size", min=1, max=50, help="Messages fetched per provider page."
    ),
    unread_only: bool = typer.Option(False, "--unread-only", help="Only inspect unread mail."),
    output: Path | None = typer.Option(  # noqa: B008 - idiomatic Typer, not a mutable default
        None, "--output", help="Write the aggregate JSON report to this path."
    ),
) -> None:
    """Inspect up to 50 messages without Tier 2, writes, or production state."""
    try:
        config = load_config()
    except ConfigLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        result = _build_report(config, limit=limit, page_size=page_size, unread_only=unread_only)
    except _ReportError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output is None:
        typer.echo(encoded, nl=False)
    else:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(encoded)
        except OSError as exc:
            typer.echo(f"Error: could not write report to {output}: {exc}", err=True)
            raise typer.Exit(code=1) from exc


def _build_report(
    config: SporkConfig, *, limit: int, page_size: int, unread_only: bool
) -> dict[str, Any]:
    """Evaluate a bounded sample using only read-side and Tier 1 components."""
    secrets = resolve_runtime_secrets(config, reason="read-only report")
    provider = build_provider(config, secrets)
    if not isinstance(provider, BackfillProvider):
        raise ReportNotSupportedError(
            f"provider {config.provider.spec!r} does not support read-only reporting"
        )

    rules = load_rules(config.rules_path)
    classifier: TextClassifier | None = (
        classify_registry.get(config.tiering.local_classifier)
        if config.tiering.local_classifier is not None
        else None
    )
    default_action = Action(type=config.tiering.default_unmatched_action)
    action_counts: Counter[str] = Counter()
    rule_counts: Counter[str] = Counter()
    body_lengths: list[int] = []
    missing_fields: Counter[str] = Counter()
    sampled = 0
    total: int | None = None
    has_more = False
    position = 0

    while sampled < limit:
        page = provider.query_messages(
            unread_only=unread_only, position=position, limit=min(page_size, limit - sampled)
        )
        total = page.total
        has_more = page.has_more
        if not page.messages:
            break
        for message in page.messages:
            if sampled >= limit:
                break
            verdict = evaluate(
                message,
                rules,
                default_unmatched_action=default_action,
                classifier=classifier,
            )
            action_counts[verdict.action.type] += 1
            if verdict.matched_rule_id is not None:
                rule_counts[verdict.matched_rule_id] += 1
            body_lengths.append(len(message.body_text))
            for field in ("from_address", "from_domain", "subject", "body_text"):
                if not getattr(message, field):
                    missing_fields[field] += 1
            sampled += 1
        position = page.next_position
        if not page.has_more:
            break

    return {
        "sampled_messages": sampled,
        "available_messages": total,
        "has_more": has_more,
        "rule_actions": dict(sorted(action_counts.items())),
        "matched_rules": dict(sorted(rule_counts.items())),
        "body_chars": {
            "min": min(body_lengths, default=0),
            "median": int(median(body_lengths)) if body_lengths else 0,
            "max": max(body_lengths, default=0),
        },
        "missing_fields": dict(sorted(missing_fields.items())),
        "tier2_calls": 0,
        "mailbox_mutations": 0,
        "messages_marked_processed": 0,
    }
