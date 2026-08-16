"""Entry point for the `sporkd` executable.

A single-command Typer app (docs/DESIGN.md §6.3) — sporkd never has
subcommands, just flags, unlike the `spork` CLI group. `--help`/
`--version` work eagerly, before any config/loop work happens.
`run()` (not `main` directly) is the registered console-script target
because `main`'s `version` argument is a `typer.Option` marker object,
not a real default — calling `main()` directly bypasses Typer's
argument parsing entirely.
"""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path

import typer

from spork import __version__
from spork.core.alerts.loader import AlerterLoadError
from spork.core.classify.registry import UnknownClassifierError
from spork.core.config.loader import ConfigLoadError, load_config
from spork.core.config.paths import configure_runtime_paths
from spork.core.config.schema import SporkConfig
from spork.core.llm.loader import LLMClientLoadError
from spork.core.logging_setup import configure_logging
from spork.core.providers.loader import ProviderLoadError
from spork.core.rules.loader import RulesLoadError
from spork.core.secrets import SecretsError
from spork.daemon.loop import run_daemon


def main(
    version: bool = typer.Option(
        False, "--version", help="Show the version and exit.", is_eager=True
    ),
    log_level: str | None = typer.Option(
        None,
        "--log-level",
        help="Override config.toml's log_level (DEBUG/INFO/WARNING/ERROR/CRITICAL).",
    ),
    config_path: str | None = typer.Option(
        None, "--config", help="Diagnostic override for the user config.toml path."
    ),
    secretspec_path: str | None = typer.Option(
        None, "--secretspec", help="Diagnostic override for the SecretSpec manifest path."
    ),
    observe: bool = typer.Option(
        False,
        "--observe",
        help="Process and audit messages without changing mail or creating drafts.",
    ),
) -> None:
    """Tiered JMAP email triage daemon. Run as a systemd user service."""
    configure_runtime_paths(
        config_path=Path(config_path).expanduser() if config_path else None,
        secretspec_path=Path(secretspec_path).expanduser() if secretspec_path else None,
    )
    if version:
        typer.echo(f"sporkd {__version__}")
        raise typer.Exit()

    try:
        config = load_config()
    except ConfigLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        configure_logging(log_level or config.log_level)
    except ValueError as exc:
        # Only logging.Logger.setLevel()'s own rejection of a bad
        # --log-level name is meant to land here — narrowly scoped so
        # an unrelated ValueError from deeper in the daemon (a real
        # bug) still surfaces as a traceback, not a swallowed "clean"
        # error.
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        asyncio.run(_run_until_signalled(config, observe=observe))
    except (
        RulesLoadError,
        ProviderLoadError,
        AlerterLoadError,
        UnknownClassifierError,
        LLMClientLoadError,
        SecretsError,
    ) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


async def _run_until_signalled(config: SporkConfig, *, observe: bool = False) -> None:
    """Runs `run_daemon()` until SIGTERM/SIGINT, then stops it cleanly.

    A `stop_event` set from a signal handler rather than relying on
    `KeyboardInterrupt`/task cancellation propagating through
    `asyncio.to_thread()` calls — those don't interrupt an in-flight
    blocking call either way (docs/DESIGN.md §6.2.1), so this is the
    same bounded-shutdown-latency tradeoff already documented there,
    not a new one.
    """
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)
    await run_daemon(config, stop_event=stop_event, observe=observe)


def run() -> None:
    """Console-script entry point registered as `sporkd` in pyproject.toml."""
    typer.run(main)


if __name__ == "__main__":
    run()
