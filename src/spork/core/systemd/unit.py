"""check_unit_status(): installed/enabled/active state of the sporkd
unit (docs/DESIGN.md §14) — what `spork doctor`'s systemd check reports.

`runner` is injected the same DI-for-subprocess pattern
`spork.cli.commands.config`'s `$EDITOR` launch already uses, so tests
never actually invoke `systemctl`. Production callers pass nothing and
get the real `subprocess.run`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from spork.core.config.paths import resolve_user_unit_path

_Runner = Callable[..., "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True, slots=True)
class UnitStatus:
    """The three facts `spork doctor` needs about the unit (docs/DESIGN.md §14).

    `enabled`/`active` are the raw `systemctl is-enabled`/`is-active`
    output (`"enabled"`, `"disabled"`, `"not-found"`, `"static"`,
    `"active"`, `"inactive"`, `"failed"`, ...) rather than a bool —
    there's real, distinct information in *which* non-good state a
    unit is in, and collapsing it to true/false would throw that away.
    `"unknown"` specifically means "couldn't ask" (no `systemctl`
    binary, or no reachable user session bus), never "asked and got a
    bad answer."
    """

    installed: bool
    enabled: str
    active: str


def _query(unit_name: str, subcommand: str, runner: _Runner) -> str:
    """One `systemctl --user <subcommand> <unit_name>` call, normalized
    to `"unknown"` on any failure that isn't systemd telling us the
    unit's actual state — a missing `systemctl` binary, or "Failed to
    connect to bus" (confirmed for real against this project's own dev
    sandbox: no systemd user session there at all). A real
    enabled/active/disabled/inactive/etc. answer is returned verbatim,
    regardless of `systemctl`'s exit code (`is-enabled`/`is-active`
    both use a non-zero exit code for perfectly legitimate "no" answers
    — the exit code alone doesn't distinguish that from "couldn't
    ask")."""
    try:
        result = runner(
            ["systemctl", "--user", subcommand, unit_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"

    if "failed to connect to bus" in result.stderr.lower():
        return "unknown"

    return result.stdout.strip() or "unknown"


def check_unit_status(
    unit_name: str = "sporkd@default",
    *,
    unit_path: Path | None = None,
    runner: _Runner = subprocess.run,
) -> UnitStatus:
    """Report whether `unit_name`'s unit file is installed, and its
    live enabled/active state.

    `installed` is a plain `Path.exists()` check against `unit_path`
    (defaulting to `resolve_user_unit_path(unit_name)`) — independent
    of whether `systemctl` itself is reachable, so a doctor run in a
    systemd-less sandbox can still say whether `spork install-service`
    has been run.
    """
    path = (
        unit_path
        if unit_path is not None
        else resolve_user_unit_path("sporkd@" if unit_name == "sporkd@default" else unit_name)
    )
    installed = path.exists()
    enabled = _query(unit_name, "is-enabled", runner)
    active = _query(unit_name, "is-active", runner)
    return UnitStatus(installed=installed, enabled=enabled, active=active)
