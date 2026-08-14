"""`spork --help` prints usage and exits 0 (docs/ROADMAP.md M0).

Graduated from an xfail spec test now that spork.cli.main uses Typer
(docs/DESIGN.md §6.3) to actually handle --help.
"""

from __future__ import annotations

import os
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


def test_log_level_option_appears_in_help() -> None:
    """docs/DESIGN.md §6.2 (M7): --log-level is real CLI surface.

    TERM=dumb forces Typer/Click's Rich help renderer to plain text —
    with color enabled (as it is on GitHub Actions' runners, unlike
    this suite's usual local/CI environment), Rich inserts an ANSI
    escape sequence between "--" and "log-level" to style the dashes
    separately, splitting this exact substring apart even though the
    visible text is unchanged. Confirmed empirically (reproduced with
    FORCE_COLOR=1, fixed with TERM=dumb), not guessed.
    """
    env = dict(os.environ)
    env["TERM"] = "dumb"

    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )

    assert result.returncode == 0
    assert "--log-level" in result.stdout


def test_an_invalid_log_level_produces_a_clean_error_not_a_traceback() -> None:
    """A typo'd --log-level fails before the subcommand (doctor, here —
    any would do) ever runs — logging.Logger.setLevel()'s own
    ValueError, caught, not a raw traceback."""
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "--log-level", "VERBOSE", "doctor"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr
