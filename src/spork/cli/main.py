"""Entry point for the `spork` executable.

A Typer command *group* (docs/DESIGN.md §6.3): `spork` grows real
subcommands (status/rules/config/logs/... — §12) milestone-by-milestone
as M5 builds them, each behind its own acceptance tests. For now it's
just enough to satisfy M0's exit criteria (`--help` works) without
inventing subcommand behavior nobody's designed yet.
"""

from __future__ import annotations

import typer

from spork import __version__
from spork.cli.commands.doctor import doctor
from spork.cli.commands.logs import logs
from spork.cli.commands.pause import pause, resume
from spork.cli.commands.rules import app as rules_app
from spork.cli.commands.status import status

app = typer.Typer(
    name="spork",
    help="Status, config, and rule management for the sporkd daemon.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(rules_app, name="rules")
app.command("doctor")(doctor)
app.command("status")(status)
app.command("pause")(pause)
app.command("resume")(resume)
app.command("logs")(logs)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False, "--version", help="Show the version and exit.", is_eager=True
    ),
) -> None:
    """Status, config, and rule management for the sporkd daemon."""
    if version:
        typer.echo(f"spork {__version__}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
