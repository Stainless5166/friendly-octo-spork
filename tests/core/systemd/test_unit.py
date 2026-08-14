"""Acceptance tests for spork.core.systemd.unit.check_unit_status() (docs/DESIGN.md §14).

`runner` is injected (mirrors spork.cli.commands.config's $EDITOR
launch DI) so these tests never actually invoke systemctl — a
sandbox/CI container commonly has no systemd user session at all
(confirmed for real against this project's own dev environment:
`systemctl --user is-active` fails with "Failed to connect to bus").
`unit_path` is injected too, so "installed" never depends on a real
$XDG_CONFIG_HOME.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from spork.core.systemd.unit import UnitStatus, check_unit_status


def _completed(stdout: str, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["systemctl"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_check_unit_status_reports_installed_enabled_active_when_all_good(
    tmp_path: Path,
) -> None:
    """The healthy case: unit file present, systemctl reports enabled/active."""
    unit_path = tmp_path / "sporkd.service"
    unit_path.write_text("[Unit]\n")

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "is-enabled" in args:
            return _completed("enabled\n")
        return _completed("active\n")

    status = check_unit_status(unit_path=unit_path, runner=runner)

    assert status == UnitStatus(installed=True, enabled="enabled", active="active")


def test_check_unit_status_reports_not_installed_when_no_unit_file_exists(
    tmp_path: Path,
) -> None:
    """No unit file at unit_path at all — a plain filesystem check,
    independent of whatever systemctl says."""
    unit_path = tmp_path / "sporkd.service"

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "is-enabled" in args:
            return _completed("not-found\n", returncode=4)
        return _completed("inactive\n", returncode=3)

    status = check_unit_status(unit_path=unit_path, runner=runner)

    assert status.installed is False
    assert status.enabled == "not-found"
    assert status.active == "inactive"


def test_check_unit_status_reports_unknown_when_systemctl_is_not_installed(
    tmp_path: Path,
) -> None:
    """No systemctl binary at all — a real, expected case on a non-systemd
    box — never crashes, reports "unknown" for both live checks."""
    unit_path = tmp_path / "sporkd.service"
    unit_path.write_text("[Unit]\n")

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("systemctl not found")

    status = check_unit_status(unit_path=unit_path, runner=runner)

    assert status.installed is True
    assert status.enabled == "unknown"
    assert status.active == "unknown"


def test_check_unit_status_reports_unknown_when_the_user_bus_is_unreachable(
    tmp_path: Path,
) -> None:
    """The confirmed-real sandbox case: systemctl exists, but
    "Failed to connect to bus" on stderr — a live-session problem, not
    an inactive/disabled unit, so it must not be reported as either."""
    unit_path = tmp_path / "sporkd.service"
    unit_path.write_text("[Unit]\n")

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _completed("", returncode=1, stderr="Failed to connect to bus: No medium found\n")

    status = check_unit_status(unit_path=unit_path, runner=runner)

    assert status.enabled == "unknown"
    assert status.active == "unknown"


def test_check_unit_status_uses_the_given_unit_name(tmp_path: Path) -> None:
    """unit_name flows through to the actual systemctl invocation."""
    unit_path = tmp_path / "other.service"
    unit_path.write_text("[Unit]\n")
    seen_args: list[list[str]] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen_args.append(args)
        return _completed("enabled\n" if "is-enabled" in args else "active\n")

    check_unit_status("other", unit_path=unit_path, runner=runner)

    assert all("other" in args for args in seen_args)
