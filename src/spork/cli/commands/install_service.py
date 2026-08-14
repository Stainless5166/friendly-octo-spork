"""`spork install-service` (docs/DESIGN.md §14).

A leaf command, registered directly on the main app (like `doctor`),
not a Typer sub-app like `rules`/`config`.
"""

from __future__ import annotations

import typer

from spork.core.systemd.install import InstallServiceError, install_service


def install_service_command(
    enable_now: bool = typer.Option(
        True,
        "--enable-now/--no-enable-now",
        help="Also run `systemctl --user enable --now` after installing the unit file.",
    ),
) -> None:
    """Install the sporkd systemd unit and (by default) enable + start it.

    Writes `systemd/sporkd.service`'s content to
    `~/.config/systemd/user/sporkd.service`, runs `systemctl --user
    daemon-reload`, and — unless `--no-enable-now` is given —
    `systemctl --user enable --now sporkd`. `loginctl enable-linger
    <user>` (wanted so `sporkd` keeps running fully logged out) is a
    documented manual step, not run here — it needs privileges this
    command has no business assuming it has.
    """
    try:
        path = install_service(enable_now=enable_now)
    except InstallServiceError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Installed unit file to {path}")
    if enable_now:
        typer.echo("Enabled and started sporkd (systemctl --user enable --now)")
    else:
        typer.echo("Run `systemctl --user enable --now sporkd` to enable and start it.")
