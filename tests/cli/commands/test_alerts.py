"""Acceptance tests for the operator alert test command."""

from __future__ import annotations

import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the real CLI entry point in a subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "alerts", "test", *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_alerts_test_help_works() -> None:
    """The beta operator can discover the alert test command."""
    result = _run("--help")

    assert result.returncode == 0
    assert "urgency" in result.stdout.lower()


def test_alerts_test_rejects_unknown_urgency_without_loading_config() -> None:
    """Invalid input fails before any backend or secret is loaded."""
    result = _run("--urgency", "urgent")

    assert result.returncode == 1
    assert "urgency must be low, normal, or critical" in result.stderr
    assert "Traceback" not in result.stderr


def test_alerts_group_is_listed_in_top_level_help() -> None:
    """The command is wired into the public CLI group."""
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "alerts" in result.stdout.lower()
