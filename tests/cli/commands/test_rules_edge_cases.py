"""Failure/edge-case tests for `spork rules test <file>`.

Companion to test_rules.py's acceptance tests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_rules_test_with_a_file_containing_no_rules_still_loads_then_hits_the_gap(
    tmp_path: Path,
) -> None:
    """A syntactically valid rules.toml with zero [[rule]] entries is
    zero rules, not an error (same as load_rules() itself) — it still
    reaches and reports the live-JMAP gap, same as a file with rules."""
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text("")

    result = _run("rules", "test", str(rules_path))

    assert result.returncode == 1
    assert "Loaded 0 rule(s)" in result.stdout
    assert "Traceback" not in result.stderr


def test_rules_test_with_no_file_argument_is_a_usage_error(tmp_path: Path) -> None:
    """Omitting the required rules_file argument entirely is Typer's
    own usage error (exit 2), not our RulesLoadError/NotImplementedError
    handling — it never reaches load_rules() at all."""
    result = _run("rules", "test")

    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_rules_group_help_lists_the_test_command() -> None:
    """`spork rules --help` lists `test` as a subcommand."""
    result = _run("rules", "--help")

    assert result.returncode == 0
    assert "test" in result.stdout.lower()
