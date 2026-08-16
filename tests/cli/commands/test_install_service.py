"""Acceptance tests for `spork install-service` (docs/DESIGN.md §14).

Subprocess-based, matching tests/cli/commands/test_doctor.py's
pattern. Real filesystem writes (isolated to tmp_path via
$XDG_CONFIG_HOME) but no real systemd session is assumed — this
sandbox has no systemd user bus (confirmed directly:
`systemctl --user daemon-reload` fails with "Failed to connect to
bus"), so these tests exercise the real failure path, not a mock of
it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def test_install_service_help_works() -> None:
    result = _run("install-service", "--help", env=dict(os.environ))

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_install_service_appears_in_top_level_help() -> None:
    result = _run("--help", env=dict(os.environ))

    assert result.returncode == 0
    assert "install-service" in result.stdout.lower()


def test_install_service_writes_the_unit_file_even_when_systemctl_fails(
    tmp_path: Path,
) -> None:
    """The write happens before daemon-reload — a systemd-less sandbox
    still gets a real, inspectable unit file on disk."""
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path)

    _run("install-service", env=env)

    assert (tmp_path / "systemd" / "user" / "sporkd@.service").exists()


def test_install_service_reports_a_clean_error_not_a_traceback(tmp_path: Path) -> None:
    """No systemd user session in this sandbox: daemon-reload fails —
    reported cleanly, never a raw traceback."""
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path)

    result = _run("install-service", env=env)

    assert result.returncode == 1
    assert "Error" in result.stderr
    assert "Traceback" not in result.stderr
