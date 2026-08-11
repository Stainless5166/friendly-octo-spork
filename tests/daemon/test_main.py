"""Not-yet-implemented spec test for `sporkd --help` (docs/ROADMAP.md M0).

Mirrors tests/cli/test_main.py's rationale for the daemon entry point —
see that file's module docstring.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.xfail(
    reason="spork.daemon.main.main() has no argument parsing yet — it "
    "unconditionally raises NotImplementedError regardless of argv. "
    "See docs/ROADMAP.md M0 and M1.",
)
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
