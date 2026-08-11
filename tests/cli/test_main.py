"""Not-yet-implemented spec test for `spork --help` (docs/ROADMAP.md M0).

M0's own exit criteria says both entry points should "produce real (if
empty) output" for --help; right now spork.cli.main.main() ignores argv
entirely and unconditionally raises NotImplementedError. This is an
xfail, not a `pytest.raises(NotImplementedError)` test — it documents
the actual target behavior (docs/DESIGN.md §12's command surface has to
start somewhere) rather than encoding today's placeholder as if it were
correct. Remove the xfail marker when a CLI framework (§6.1: click or
typer, not yet chosen) actually handles --help.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.xfail(
    reason="spork.cli.main.main() has no argument parsing yet — it "
    "unconditionally raises NotImplementedError regardless of argv. "
    "See docs/ROADMAP.md M0 and M5.",
)
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
