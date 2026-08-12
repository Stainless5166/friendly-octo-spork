"""`spork logs` (docs/DESIGN.md §6.2.2/§13).

Doesn't touch the control socket at all — `audit_log` is a `StateDB`
table, readable directly whether or not `sporkd` is running, the same
reasoning that already lets rules/config file edits work with the
daemon stopped (§6.3).
"""

from __future__ import annotations

import typer

from spork.core.config.loader import ConfigLoadError, load_config
from spork.core.state.db import StateDB


def logs(
    tail: int | None = typer.Option(  # noqa: B008 - idiomatic Typer, not a mutable default
        None, "--tail", help="Show only the last N entries."
    ),
    since: str | None = typer.Option(  # noqa: B008
        None, "--since", help="Only entries with a timestamp at or after this ISO 8601 value."
    ),
    message_id: str | None = typer.Option(  # noqa: B008
        None, "--message-id", help="Only entries for this JMAP message ID."
    ),
) -> None:
    """Print audit_log entries, oldest first.

    A fresh install (or a daemon that's never run) prints nothing, not
    an error — `StateDB` creates its schema on first open regardless
    of whether anything has ever been written to it.
    """
    try:
        config = load_config()
    except ConfigLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    with StateDB(config.db_path) as db:
        entries = db.get_audit_entries(jmap_id=message_id)

    if since is not None:
        entries = [entry for entry in entries if entry.ts >= since]
    if tail is not None:
        entries = entries[-tail:]

    for entry in entries:
        detail = f" {entry.detail_json}" if entry.detail_json else ""
        typer.echo(f"{entry.ts} {entry.jmap_id} {entry.event}{detail}")
