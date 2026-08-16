"""Entry point for the `spork` executable.

A Typer command *group* (docs/DESIGN.md §6.3): `spork` grows real
subcommands (status/rules/config/logs/... — §12) milestone-by-milestone
as M5 builds them, each behind its own acceptance tests. For now it's
just enough to satisfy M0's exit criteria (`--help` works) without
inventing subcommand behavior nobody's designed yet.
"""

from __future__ import annotations

from pathlib import Path

import typer

from spork import __version__
from spork.cli.commands.backfill import backfill
from spork.cli.commands.config import app as config_app
from spork.cli.commands.doctor import doctor
from spork.cli.commands.install_service import install_service_command
from spork.cli.commands.logs import logs
from spork.cli.commands.pause import pause, resume
from spork.cli.commands.reclassify import reclassify
from spork.cli.commands.rules import app as rules_app
from spork.cli.commands.secrets import app as secrets_app
from spork.cli.commands.status import status
from spork.core.config.paths import configure_runtime_paths
from spork.core.logging_setup import configure_logging

app = typer.Typer(
    name="spork",
    help="Status, config, and rule management for the sporkd daemon.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(rules_app, name="rules")
app.add_typer(config_app, name="config")
app.add_typer(secrets_app, name="secrets")
app.command("doctor")(doctor)
app.command("status")(status)
app.command("pause")(pause)
app.command("resume")(resume)
app.command("logs")(logs)
app.command("reclassify")(reclassify)
app.command("backfill")(backfill)
app.command("install-service")(install_service_command)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False, "--version", help="Show the version and exit.", is_eager=True
    ),
    log_level: str = typer.Option(
        "WARNING",
        "--log-level",
        help="Log verbosity (DEBUG/INFO/WARNING/ERROR/CRITICAL) — quiet by default, "
        "this is a short-lived CLI, not the daemon (§6.2).",
    ),
    config_path: str | None = typer.Option(
        None, "--config", help="Diagnostic override for the user config.toml path."
    ),
    secretspec_path: str | None = typer.Option(
        None, "--secretspec", help="Diagnostic override for the SecretSpec manifest path."
    ),
) -> None:
    """Status, config, and rule management for the sporkd daemon."""
    configure_runtime_paths(
        config_path=Path(config_path).expanduser() if config_path else None,
        secretspec_path=Path(secretspec_path).expanduser() if secretspec_path else None,
    )
    if version:
        typer.echo(f"spork {__version__}")
        raise typer.Exit()

    try:
        configure_logging(log_level)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
