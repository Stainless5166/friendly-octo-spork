"""`spork config` subcommands (docs/DESIGN.md §7.2/§13).

`show` surfaces the fully-merged effective config, flagging every
value the enforced tier sets (regardless of whether a lower tier
already agreed with it) and redacting anything that looks like a
credential. `edit` only ever touches the *user* tier — the
system-default and enforced tiers are edited directly with real
filesystem permissions (§7.2) — and never pushes a live reload to a
running `sporkd`: unlike rules, config controls the
`Provider`/`LLMClient`/`Alerter` objects `run_daemon()` builds once at
startup, not a plain list re-read every poll cycle, so "restart to
apply" is the honest answer here, not a shortcut.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import typer

from spork.core.config.loader import ConfigLoadError, enforced_override_paths, load_config
from spork.core.config.paths import resolve_user_config_path
from spork.core.config.schema import SporkConfig, TieringConfig
from spork.core.state.db import StateDB

app = typer.Typer(
    name="config",
    help="Inspect and edit spork's config.toml.",
    no_args_is_help=True,
)

# Case-insensitive substrings that mark a kwargs key as probably holding
# a credential — a heuristic, not a guarantee (docs/DESIGN.md §7.2):
# §7.3's secrets model says a real credential shouldn't be in
# config.toml at all, but `show` doesn't get to assume every file was
# authored correctly.
_SECRET_KEY_MARKERS = ("token", "key", "secret", "password")


def _looks_like_secret(key: str) -> bool:
    key_lower = key.lower()
    return any(marker in key_lower for marker in _SECRET_KEY_MARKERS)


def _format_show_lines(config: SporkConfig, enforced_paths: set[str]) -> list[str]:
    """Every `SporkConfig` field as one `path = value` line, `path`
    dotted to match `enforced_override_paths()`'s own dotted paths.

    A closed, hand-written walk over `SporkConfig`'s known fields —
    not a generic model-introspection routine — the same "this schema
    is small and fixed, so serialize it directly" choice
    `spork.core.rules.writer.dump_rules()` makes.
    """
    lines: list[str] = []

    def _add(path: str, value: object) -> None:
        suffix = " (enforced)" if path in enforced_paths else ""
        lines.append(f"{path} = {value}{suffix}")

    _add("rules_path", config.rules_path)
    _add("db_path", config.db_path)
    _add("socket_path", config.socket_path)

    for section in ("provider", "llm", "alerts"):
        spec = getattr(config, section)
        _add(f"{section}.spec", spec.spec)
        for key, value in spec.kwargs.items():
            display = "<redacted>" if _looks_like_secret(key) else value
            _add(f"{section}.kwargs.{key}", display)
        for key, value in spec.secret_kwargs.items():
            _add(f"{section}.secret_kwargs.{key}", value)

    if config.llm_recording is not None:
        _add("llm_recording.corpus_path", config.llm_recording.corpus_path)

    for field in TieringConfig.model_fields:
        _add(f"tiering.{field}", getattr(config.tiering, field))

    return lines


def _load_config_or_exit() -> SporkConfig:
    try:
        return load_config()
    except ConfigLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("init")
def init(
    force: bool = typer.Option(False, "--force", help="Replace an existing user config."),
    model: str = typer.Option(
        "anthropic/claude-sonnet-5",
        help="LiteLLM model identifier for Tier 2.",
    ),
) -> None:
    """Create a safe JMAP/LiteLLM user configuration and starter rules file."""
    config_path = resolve_user_config_path()
    if config_path.exists() and not force:
        typer.echo(
            f"Error: config already exists at {config_path}; use --force to replace it.",
            err=True,
        )
        raise typer.Exit(code=1)

    rules_path = config_path.parent / "rules.toml"
    data_dir = Path.home() / ".local" / "share" / "spork"
    config_text = f"""rules_path = {json.dumps(str(rules_path))}
db_path = {json.dumps(str(data_dir / "state.sqlite3"))}

[provider]
spec = "spork.core.providers.jmap.provider:JmapProvider"
[provider.kwargs]
host = "api.fastmail.com"
poll_interval_seconds = 30.0
[provider.secret_kwargs]
api_token = "JMAP_API_TOKEN"

[llm]
spec = "spork.core.llm.clients.litellm:LiteLLMClient"
[llm.kwargs]
model = {json.dumps(model)}
[llm.secret_kwargs]
api_key = "ANTHROPIC_API_KEY"

[alerts]
spec = "spork.core.alerts.log:LoggingAlerter"

[tiering]
tier2_enabled = false
default_unmatched_action = "ignore"
"""
    rules_text = """[[rule]]
id = "starter-ignore"
description = "Disabled starter rule; add explicit rules before enabling triage."
enabled = false
when = { always = true }
action = { type = "ignore", reason = "starter configuration" }
"""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_text)
        rules_path.write_text(rules_text)
    except OSError as exc:
        typer.echo(f"Error: could not write configuration: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Created {config_path}")
    typer.echo(f"Created {rules_path}")
    typer.echo("Edit rules.toml, then run spork doctor before starting sporkd.")


@app.command("show")
def show() -> None:
    """Print the fully-merged effective config (docs/DESIGN.md §13).

    Credential-shaped `kwargs` values are redacted; SecretSpec names
    in `secret_kwargs` remain visible. Every value the enforced tier
    sets is flagged `(enforced)`.
    """
    config = _load_config_or_exit()
    enforced_paths = enforced_override_paths()
    for line in _format_show_lines(config, enforced_paths):
        typer.echo(line)


@app.command("edit")
def edit() -> None:
    """Open the *user* tier's config.toml in $EDITOR, validate the real
    merged result on save (docs/DESIGN.md §7.2/§13).

    Never pushes a live reload — config controls objects `run_daemon()`
    only ever builds once at startup; "restart sporkd to apply" is
    printed instead. A save that fails validation is reported as a
    clean error, and the file is left exactly as $EDITOR wrote it.
    """
    # Loaded once up front purely to give a clean error if there's no
    # usable config at all yet to edit — the actual save is validated
    # again below, against whatever $EDITOR produces.
    _load_config_or_exit()

    user_config_path = resolve_user_config_path()
    editor = shlex.split(os.environ.get("EDITOR", "vi"))
    subprocess.call([*editor, str(user_config_path)])

    config = _load_config_or_exit()
    with StateDB(config.db_path) as db:
        db.write_control_plane_audit_entry(
            ts=datetime.now(UTC).isoformat(),
            event="config_edit",
            detail_json=json.dumps({"path": str(user_config_path)}),
        )
    typer.echo("Saved. Restart sporkd to apply.")
