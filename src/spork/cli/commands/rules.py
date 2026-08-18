"""`spork rules` subcommands (docs/DESIGN.md §12/§13, live reload §6.2.2/§7.5)."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import typer

from spork.core.config.loader import ConfigLoadError, load_config
from spork.core.config.paths import resolve_socket_path
from spork.core.config.schema import SporkConfig
from spork.core.ipc.client import IpcConnectionError, send_request
from spork.core.providers.base import BackfillProvider
from spork.core.providers.loader import ProviderLoadError
from spork.core.rules.engine import evaluate
from spork.core.rules.loader import RulesLoadError, load_rules
from spork.core.rules.schema import Action, Rule
from spork.core.rules.writer import dump_rules
from spork.core.runtime import build_provider, resolve_runtime_secrets
from spork.core.secrets import SecretsError
from spork.core.state.db import StateDB

app = typer.Typer(
    name="rules",
    help="Inspect, edit, and dry-run rules.toml files.",
    no_args_is_help=True,
)


@app.command("test")
def test(
    rules_file: Path = typer.Argument(  # noqa: B008 - idiomatic Typer, not a mutable default
        ..., help="Path to a rules.toml file to dry-run."
    ),
) -> None:
    """Dry-run a rules.toml file against recent mail without side effects."""
    try:
        rules = load_rules(rules_file)
    except RulesLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Loaded {len(rules)} rule(s) from {rules_file}.")
    try:
        _dry_run_against_recent_mail(rules)
    except (ConfigLoadError, ProviderLoadError, SecretsError, RulesTestError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


class RulesTestError(Exception):
    """One CLI boundary for unsupported or failed read-only rule previews."""


def _dry_run_against_recent_mail(rules: Sequence[Rule]) -> None:
    """Fetch and evaluate a bounded recent-mail sample without pipeline state."""
    try:
        config = load_config()
        secrets = resolve_runtime_secrets(config, reason="rules dry-run")
        provider = build_provider(config, secrets)
    except (ConfigLoadError, ProviderLoadError, SecretsError):
        raise
    except Exception as exc:
        raise RulesTestError(f"could not load the configured provider: {exc}") from exc

    if not isinstance(provider, BackfillProvider):
        raise RulesTestError(
            f"provider {config.provider.spec!r} does not support read-only message queries"
        )

    try:
        page = provider.query_messages(limit=50)
    except Exception as exc:
        raise RulesTestError(f"could not fetch recent mail: {exc}") from exc

    for message in page.messages:
        verdict = evaluate(
            message,
            rules,
            default_unmatched_action=Action(type=config.tiering.default_unmatched_action),
        )
        typer.echo(
            json.dumps(
                {
                    "action": {
                        "mailbox": verdict.action.mailbox,
                        "reason": verdict.action.reason,
                        "type": verdict.action.type,
                    },
                    "matched_rule_id": verdict.matched_rule_id,
                    "message_id": message.message_id,
                },
                sort_keys=True,
            )
        )

    typer.echo(f"Previewed {len(page.messages)} recent message(s); no changes made.")


@app.command("validate")
def validate(
    rules_file: Path | None = typer.Argument(  # noqa: B008 - idiomatic Typer default
        None, help="Rules file; defaults to the configured rules.toml."
    ),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Validate a ruleset and report whether it is safe for Tier 1 beta use."""
    config = _load_config_or_exit()
    path = rules_file or config.rules_path
    rules = _load_rules_or_exit(path)
    enabled = [rule for rule in rules if rule.enabled]
    action_counts: dict[str, int] = {}
    for rule in enabled:
        action_counts[rule.action.type] = action_counts.get(rule.action.type, 0) + 1
    escalation_rules = [rule.id for rule in enabled if rule.action.type == "escalate"]
    provider_kwargs = config.provider.kwargs
    writes_enabled = provider_kwargs.get("allow_writes") is True
    expected_account = provider_kwargs.get("expected_account_email")
    result = {
        "action_counts": dict(sorted(action_counts.items())),
        "enabled_rules": len(enabled),
        "escalation_rules": escalation_rules,
        "expected_account_configured": isinstance(expected_account, str) and bool(expected_account),
        "path": str(path),
        "safe_for_tier1": not escalation_rules and (not writes_enabled or bool(expected_account)),
        "tier2_backend": config.llm.spec,
        "total_rules": len(rules),
        "writes_enabled": writes_enabled,
    }
    if json_output:
        typer.echo(json.dumps(result, sort_keys=True))
    else:
        typer.echo(f"Rules: {len(enabled)} enabled / {len(rules)} total")
        typer.echo(f"Actions: {json.dumps(result['action_counts'], sort_keys=True)}")
        typer.echo(f"Tier 2 escalation rules: {len(escalation_rules)}")
        typer.echo(f"Writes enabled: {writes_enabled}")
        typer.echo(f"Expected account configured: {result['expected_account_configured']}")
        typer.echo(f"Safe for Tier 1 beta: {result['safe_for_tier1']}")
    if not result["safe_for_tier1"]:
        raise typer.Exit(code=1)


def _load_config_or_exit() -> SporkConfig:
    try:
        return load_config()
    except ConfigLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _load_rules_or_exit(rules_path: Path) -> list[Rule]:
    try:
        return load_rules(rules_path)
    except RulesLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("list")
def list_rules() -> None:
    """Print every rule in the configured rules.toml: id, enabled/
    disabled, and its action (docs/DESIGN.md §13).

    Per-rule match counts aren't tracked anywhere — that's a separate,
    still-unbuilt `rule_stats` table behind a different, not-yet-designed
    command (§7.4), not something this prints as if it existed.
    """
    config = _load_config_or_exit()
    rules = _load_rules_or_exit(config.rules_path)

    if not rules:
        typer.echo("No rules configured.")
        return

    for rule in rules:
        status = "enabled" if rule.enabled else "disabled"
        summary = f"{rule.id} [{status}] {rule.action.type}"
        if rule.action.mailbox:
            summary += f" -> {rule.action.mailbox}"
        if rule.description:
            summary += f" — {rule.description}"
        typer.echo(summary)


@app.command("edit")
def edit() -> None:
    """Open rules.toml in $EDITOR, validate on save, push a reload to
    a running sporkd (docs/DESIGN.md §6.2.2/§13).

    A save that fails validation is reported as a clean error and
    never pushes a reload — the file on disk is left exactly as
    $EDITOR wrote it, for the user to fix and try again.
    """
    config = _load_config_or_exit()

    editor = shlex.split(os.environ.get("EDITOR", "vi"))
    subprocess.call([*editor, str(config.rules_path)])

    _load_rules_or_exit(config.rules_path)
    _push_reload(config.socket_path)
    typer.echo("Saved.")


def _set_enabled(rule_id: str, *, enabled: bool) -> None:
    config = _load_config_or_exit()
    rules = _load_rules_or_exit(config.rules_path)

    if not any(rule.id == rule_id for rule in rules):
        typer.echo(f"Error: no rule with id {rule_id!r} in {config.rules_path}", err=True)
        raise typer.Exit(code=1)

    updated = [
        rule.model_copy(update={"enabled": enabled}) if rule.id == rule_id else rule
        for rule in rules
    ]
    config.rules_path.write_text(dump_rules(updated))
    with StateDB(config.db_path) as db:
        db.write_control_plane_audit_entry(
            ts=datetime.now(UTC).isoformat(),
            event="rules_enable" if enabled else "rules_disable",
            detail_json=json.dumps({"rule_id": rule_id}),
        )
    _push_reload(config.socket_path)
    typer.echo(f"{rule_id}: {'enabled' if enabled else 'disabled'}.")


@app.command("enable")
def enable(
    rule_id: str = typer.Argument(..., help="The id of the rule to enable."),  # noqa: B008
) -> None:
    """Enable one rule by id, rewrite rules.toml, push a reload (docs/DESIGN.md §7.5).

    Rewrites the whole file from the validated Rule models — real,
    stated tradeoff: comments/formatting in a hand-edited rules.toml
    don't survive this (§7.5). `spork rules edit` is unaffected.
    """
    _set_enabled(rule_id, enabled=True)


@app.command("disable")
def disable(
    rule_id: str = typer.Argument(..., help="The id of the rule to disable."),  # noqa: B008
) -> None:
    """Disable one rule by id — same mechanics/tradeoff as `enable` (docs/DESIGN.md §7.5)."""
    _set_enabled(rule_id, enabled=False)


def _push_reload(socket_path: Path | None) -> None:
    """Best-effort: a save always succeeds on its own merits (the file
    is already validated by the time this runs) — reaching a running
    sporkd is a bonus, never something that turns a successful save
    into a reported failure (docs/DESIGN.md §6.2.2/§7.5)."""
    socket_path = socket_path if socket_path is not None else resolve_socket_path()
    try:
        response = send_request(socket_path, "reload")
    except IpcConnectionError:
        typer.echo("sporkd is not running — changes will apply on next start.")
        return
    if response.ok:
        rule_count = response.data.get("rule_count", "?")
        typer.echo(f"sporkd reloaded ({rule_count} rule(s)).")
    else:
        typer.echo(f"Warning: sporkd rejected the reload: {response.error}", err=True)
