"""Alert delivery checks for the local beta operator experience."""

from __future__ import annotations

import typer

from spork.core.alerts.loader import AlerterLoadError
from spork.core.config.loader import ConfigLoadError, load_config
from spork.core.runtime import build_alerter, resolve_runtime_secrets
from spork.core.secrets import SecretsError

app = typer.Typer(
    name="alerts",
    help="Inspect and test configured alert delivery.",
    no_args_is_help=True,
)


@app.command("test")
def test(
    message: str = typer.Option(  # noqa: B008 - idiomatic Typer default
        "Spork beta alert test",
        "--message",
        help="Message delivered through the configured alerter.",
    ),
    urgency: str = typer.Option(  # noqa: B008 - idiomatic Typer default
        "normal",
        "--urgency",
        help="Alert urgency: low, normal, or critical.",
    ),
) -> None:
    """Send one operator-visible alert without involving mail or the daemon."""
    if urgency not in {"low", "normal", "critical"}:
        typer.echo("Error: urgency must be low, normal, or critical", err=True)
        raise typer.Exit(code=1)
    try:
        config = load_config()
        secrets = resolve_runtime_secrets(config, reason="alert delivery test")
        alerter = build_alerter(config, secrets)
        alerter.notify("Spork alert test", message, urgency=urgency)  # type: ignore[arg-type]
    except (AlerterLoadError, ConfigLoadError, SecretsError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("Alert sent through the configured alerter.")
