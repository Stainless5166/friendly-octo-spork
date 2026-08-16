"""`spork secrets` commands for local SecretSpec enrollment."""

from __future__ import annotations

import time

import typer

from spork.core.config.paths import resolve_secretspec_path
from spork.core.secret_store import SecretStoreError, store_secret
from spork.core.secrets import SecretsError, resolve_secrets

app = typer.Typer(
    name="secrets",
    help="Enroll required credentials in the OS keyring.",
    no_args_is_help=False,
)

_SECRET_NAMES = ("JMAP_API_TOKEN", "ANTHROPIC_API_KEY")


@app.callback(invoke_without_command=True)
def secrets_group(ctx: typer.Context) -> None:
    """Keep bare `spork secrets` as the enrollment shorthand."""
    if ctx.invoked_subcommand is None:
        enroll()


@app.command()
def enroll() -> None:
    """Prompt for Spork's required credentials and store them in the OS keyring."""
    values: dict[str, str] = {}
    for name in _SECRET_NAMES:
        values[name] = typer.prompt(name, hide_input=True, confirmation_prompt=True)

    manifest_path = resolve_secretspec_path()
    try:
        for name, value in values.items():
            store_secret(manifest_path, name, value)
    except SecretStoreError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Stored JMAP_API_TOKEN and ANTHROPIC_API_KEY in the OS keyring.")


@app.command()
def wait(
    timeout: float = typer.Option(120.0, min=0.0, help="Maximum seconds to wait."),
    interval: float = typer.Option(1.0, min=0.05, help="Seconds between keyring checks."),
) -> None:
    """Wait until all required credentials are available in the OS keyring."""
    deadline = time.monotonic() + timeout
    manifest_path = resolve_secretspec_path()
    while True:
        try:
            resolve_secrets(manifest_path, reason="wait for sporkd startup")
            return
        except SecretsError as exc:
            if time.monotonic() >= deadline:
                typer.echo(f"Error: credentials not ready: {exc}", err=True)
                raise typer.Exit(code=1) from exc
            time.sleep(interval)
