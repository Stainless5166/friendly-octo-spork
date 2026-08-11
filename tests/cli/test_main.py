"""`spork --help` prints usage and exits 0 (docs/ROADMAP.md M0).

Graduated from an xfail spec test now that spork.cli.main uses Typer
(docs/DESIGN.md §6.3) to actually handle --help.
"""

from __future__ import annotations

import subprocess
import sys


def test_help_prints_usage_and_exits_zero() -> None:
    """`spork --help` should exit 0 and print usage text, not crash."""
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
    assert "Traceback" not in result.stderr


def test_version_prints_the_installed_version_and_exits_zero() -> None:
    """`spork --version` should exit 0 and print spork's own version."""
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "spork" in result.stdout.lower()
