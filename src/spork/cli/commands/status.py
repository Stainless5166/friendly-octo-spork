"""`spork status` (docs/DESIGN.md §6.2.2/§13).

A leaf command, registered directly on the main app (like `doctor`),
not a Typer sub-app like `rules`.
"""

from __future__ import annotations

import typer

from spork.core.config.loader import ConfigLoadError, load_config
from spork.core.config.paths import resolve_socket_path
from spork.core.ipc.client import IpcConnectionError, send_request


def status() -> None:
    """Report whether `sporkd` is running, paused, and since when.

    "Push connection state"/"queue depth"/"LLM spend" aren't reported
    — nothing in this architecture tracks them yet (docs/DESIGN.md
    §6.2.2). A daemon that isn't running produces a clear message, not
    a raw connection error.
    """
    try:
        config = load_config()
    except ConfigLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    socket_path = config.socket_path if config.socket_path is not None else resolve_socket_path()

    try:
        response = send_request(socket_path, "status")
    except IpcConnectionError:
        typer.echo("sporkd is not running (start it with: systemctl --user start sporkd)", err=True)
        raise typer.Exit(code=1) from None

    if not response.ok:
        typer.echo(f"Error: {response.error}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"paused: {response.data.get('paused')}")
    typer.echo(f"started_at: {response.data.get('started_at')}")
