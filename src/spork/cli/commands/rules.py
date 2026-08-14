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
from spork.core.rules.loader import RulesLoadError, load_rules
from spork.core.rules.schema import Rule
from spork.core.rules.writer import dump_rules
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
    """Dry-run a rules.toml file against recent mail (docs/DESIGN.md §13).

    Loads and validates the file first — real, useful on its own, and
    catches a malformed rules.toml here rather than as a crash once it
    reaches the daemon. Actually running it against recent mail needs a
    live JMAP connection (docs/DESIGN.md §9.3, §13): spork has no local
    mail store to substitute for one, so that part isn't implemented
    until M1's real JMAP fetch exists — this fails loud rather than
    faking a result.
    """
    try:
        rules = load_rules(rules_file)
    except RulesLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Loaded {len(rules)} rule(s) from {rules_file}.")

    # Caught and re-reported as a clean message rather than left to
    # propagate: this is a genuinely unimplemented feature (real
    # NotImplementedError semantics, see spork.core.rules.loader's
    # docstring and docs/ROADMAP.md M1), not a bug — a user shouldn't
    # see a stack trace for "this part isn't built yet."
    try:
        _dry_run_against_recent_mail(rules)
    except NotImplementedError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _dry_run_against_recent_mail(rules: Sequence[Rule]) -> None:
    """The part that genuinely needs a live JMAP connection (docs/DESIGN.md §13).

    Spork has no local mail store to substitute for "recent mail" —
    fetching it here means a real `JmapClient.fetch_new_messages()`
    call, which is itself a settled-shape `NotImplementedError` stub
    pending a live Fastmail account (docs/ROADMAP.md M1). This function
    exists so that blocker has one clearly-named place to live, instead
    of being inlined into the command body.
    """
    raise NotImplementedError(
        "spork rules test requires a live JMAP connection to fetch recent mail — "
        "not implemented yet, see docs/ROADMAP.md M1"
    )


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
