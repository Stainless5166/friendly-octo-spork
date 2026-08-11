"""`spork doctor` (docs/DESIGN.md §12).

A leaf command (no subcommands), unlike `rules` — registered directly
on the main app in `spork.cli.main`.
"""

from __future__ import annotations

import typer


def doctor() -> None:
    """Check JMAP auth/connectivity (docs/DESIGN.md §12).

    docs/DESIGN.md §12 describes `spork doctor` as covering secrets
    (`secretspec check`), JMAP auth/connectivity, systemd unit status,
    and DB migration status. Only JMAP connectivity has a settled
    shape today — it genuinely needs a live `JmapClient.connect()`
    call to report anything real (docs/ROADMAP.md M1), so it's a
    settled-shape `NotImplementedError`, caught and reported as a
    clean error rather than a raw traceback, same as `spork rules
    test`'s live-fetch gap. The other three checks need pieces that
    don't exist yet either (`spork.core.config` for secrets/DB path
    resolution, M6 packaging for the systemd unit) — this command
    doesn't pretend to run them until they do.
    """
    try:
        _check_jmap_connectivity()
    except NotImplementedError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _check_jmap_connectivity() -> None:
    """The part that genuinely needs a live JMAP session (docs/ROADMAP.md M1).

    Mirrors `JmapClient.connect()`'s own stub directly: `spork doctor`
    reporting connectivity state means calling it, and there's nothing
    real to report until that call is.
    """
    raise NotImplementedError(
        "spork doctor's JMAP auth/connectivity check requires a live JMAP "
        "connection — not implemented yet, see docs/ROADMAP.md M1"
    )
