"""Entry point for the `sporkd` executable.

A single-command Typer app (docs/DESIGN.md §6.3) — sporkd never has
subcommands, just flags, unlike the `spork` CLI group. `--help`/
`--version` work now; the actual event loop (JMAP session, push
listener, rule engine, action executor, alerting, control socket —
§6.2) lands incrementally across the roadmap milestones
(docs/ROADMAP.md), each behind its own acceptance tests. `run()` (not
`main` directly) is the registered console-script target because
`main`'s `version` argument is a `typer.Option` marker object, not a
real default — calling `main()` directly bypasses Typer's argument
parsing entirely.
"""

from __future__ import annotations

import typer

from spork import __version__


def main(
    version: bool = typer.Option(
        False, "--version", help="Show the version and exit.", is_eager=True
    ),
) -> None:
    """Tiered JMAP email triage daemon. Run as a systemd user service."""
    if version:
        typer.echo(f"sporkd {__version__}")
        raise typer.Exit()
    raise NotImplementedError(
        "sporkd's daemon loop is not implemented yet — see docs/ROADMAP.md for milestone status."
    )


def run() -> None:
    """Console-script entry point registered as `sporkd` in pyproject.toml."""
    typer.run(main)


if __name__ == "__main__":
    run()
