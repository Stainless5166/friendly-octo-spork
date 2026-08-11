"""Acceptance tests for `spork doctor` (docs/DESIGN.md §12).

Subprocess-based, matching tests/cli/commands/test_rules.py's pattern.
`spork doctor`'s JMAP auth/connectivity check genuinely needs a live
JMAP session (docs/ROADMAP.md M1) — same settled-shape-stub treatment
as `JmapClient.connect()` and `spork rules test`'s live-fetch gap: the
shape is settled and it fails clearly, not silently or with a raw
traceback.
"""

from __future__ import annotations

import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_doctor_help_works() -> None:
    """`spork doctor --help` exits 0 and prints usage, not a crash."""
    result = _run("doctor", "--help")

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_doctor_reports_a_clean_error_not_a_traceback() -> None:
    """`spork doctor` fails on the JMAP connectivity gap with a clean,
    specific error — never a raw traceback."""
    result = _run("doctor")

    assert result.returncode == 1
    assert "Error" in result.stderr
    assert "Traceback" not in result.stderr


def test_doctor_appears_in_top_level_help() -> None:
    """`spork --help` lists `doctor` as a command — confirms it's
    actually wired into the app, not just importable."""
    result = _run("--help")

    assert result.returncode == 0
    assert "doctor" in result.stdout.lower()
