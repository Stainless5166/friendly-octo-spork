"""`sporkd --help` prints usage and exits 0 (docs/ROADMAP.md M0).

Graduated from an xfail spec test now that spork.daemon.main uses
Typer (docs/DESIGN.md §6.3) to actually handle --help. Mirrors
tests/cli/test_main.py for the daemon entry point.
"""

from __future__ import annotations

import subprocess
import sys


def test_help_prints_usage_and_exits_zero() -> None:
    """`sporkd --help` should exit 0 and print usage text, not crash."""
    result = subprocess.run(
        [sys.executable, "-m", "spork.daemon.main", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
    assert "Traceback" not in result.stderr


def test_version_prints_the_installed_version_and_exits_zero() -> None:
    """`sporkd --version` should exit 0 and print sporkd's own version,
    without falling through to the NotImplementedError daemon loop."""
    result = subprocess.run(
        [sys.executable, "-m", "spork.daemon.main", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "sporkd" in result.stdout.lower()
