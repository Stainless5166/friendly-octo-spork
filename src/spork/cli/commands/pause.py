"""`spork pause` / `spork resume` (docs/DESIGN.md §6.2.2/§13).

Two leaf commands, one file — mirroring the component tree's own
`pause.py<br/>spork pause/resume` node (§6.1).
"""

from __future__ import annotations

import typer

from spork.core.config.loader import ConfigLoadError, load_config
from spork.core.config.paths import resolve_socket_path
from spork.core.ipc.client import IpcConnectionError, send_request


def _send_control_command(command: str) -> None:
    """Shared plumbing for both commands: load config, reach the
    socket, print the result or a clean "daemon not running" message."""
    try:
        config = load_config()
    except ConfigLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    socket_path = config.socket_path if config.socket_path is not None else resolve_socket_path()

    try:
        response = send_request(socket_path, command)
    except IpcConnectionError:
        typer.echo("sporkd is not running (start it with: systemctl --user start sporkd)", err=True)
        raise typer.Exit(code=1) from None

    if not response.ok:
        typer.echo(f"Error: {response.error}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"paused: {response.data.get('paused')}")


def pause() -> None:
    """Stop Tier 1 processing without killing the daemon.

    §6.2.2's honest caveat: this also stops fetching new mail, not
    just acting on what's already fetched — `Source.poll()` fuses
    "wait" and "fetch" into one call, so there's no way yet to keep a
    push connection live while skipping only the acting-on-it part.
    """
    _send_control_command("pause")


def resume() -> None:
    """Resume Tier 1 processing after `spork pause`."""
    _send_control_command("resume")
