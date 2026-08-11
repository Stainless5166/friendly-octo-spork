"""Acceptance tests for `spork rules test <file>` (docs/DESIGN.md §12/§13).

Subprocess-based, matching tests/cli/test_main.py's pattern: exercises
the real installed console-script entry point, not an in-process Typer
CliRunner, so what's tested is exactly what a user actually runs.

Rules loading/validation is real and fully testable now
(spork.core.rules.loader). Actually dry-running "against recent mail"
needs a live JMAP fetch that doesn't exist yet (docs/ROADMAP.md M1) —
there's no fixture-file substitute for that (docs/DESIGN.md §13), so
this command loads+validates for real and then fails clearly with a
NotImplementedError for the rest, the same settled-shape-stub pattern
as JmapClient.fetch_new_messages().
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


def test_rules_test_help_works() -> None:
    """`spork rules test --help` exits 0 and prints usage, not a crash."""
    result = _run("rules", "test", "--help")

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_rules_test_with_a_valid_file_loads_then_fails_on_the_live_jmap_gap(
    tmp_path: Path,
) -> None:
    """A well-formed rules.toml loads successfully (real output proving
    that part isn't stubbed) before the command fails clearly on the
    live-JMAP-fetch gap it genuinely can't cross yet."""
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
        [[rule]]
        id = "catch-newsletter"
        when = { from_domain_in = ["newsletter.example.com"] }
        action = { type = "move", mailbox = "Reading" }
        """
    )

    result = _run("rules", "test", str(rules_path))

    assert result.returncode == 1
    assert "Loaded 1 rule" in result.stdout
    assert "Traceback" not in result.stderr


def test_rules_test_with_an_invalid_file_reports_a_clean_error(tmp_path: Path) -> None:
    """A malformed rules.toml is reported as a clean, specific error —
    never a raw traceback — and the command never reaches the
    live-JMAP-fetch gap at all, since it never got a valid rules list."""
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text("this is not [ valid toml")

    result = _run("rules", "test", str(rules_path))

    assert result.returncode == 1
    assert "Error" in result.stderr
    assert "Traceback" not in result.stderr


def test_rules_test_with_a_missing_file_reports_a_clean_error(tmp_path: Path) -> None:
    """A path that doesn't exist gets the same clean-error treatment as
    a malformed file, not a raw FileNotFoundError traceback."""
    result = _run("rules", "test", str(tmp_path / "does-not-exist.toml"))

    assert result.returncode == 1
    assert "Error" in result.stderr
    assert "Traceback" not in result.stderr


def test_rules_group_appears_in_top_level_help() -> None:
    """`spork --help` lists the `rules` subcommand group — confirms
    app.add_typer() wiring, not just that the rules module imports."""
    result = _run("--help")

    assert result.returncode == 0
    assert "rules" in result.stdout.lower()
