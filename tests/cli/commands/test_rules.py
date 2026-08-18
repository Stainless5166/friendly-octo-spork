"""Acceptance tests for `spork rules test <file>` (docs/DESIGN.md §12/§13).

Subprocess-based, matching tests/cli/test_main.py's pattern: exercises
the real CLI entry point, including the read-only BackfillProvider path.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def test_rules_test_help_works() -> None:
    """`spork rules test --help` exits 0 and prints usage, not a crash."""
    result = _run("rules", "test", "--help")

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_rules_test_fetches_and_evaluates_recent_messages_without_writes(
    tmp_path: Path,
) -> None:
    """A valid rules file previews FileProvider mail without applying actions."""
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
        [[rule]]
        id = "catch-newsletter"
        when = { from_domain_in = ["newsletter.example.com"] }
        action = { type = "move", mailbox = "Reading" }
        """
    )
    messages_path = tmp_path / "messages.json"
    messages_path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-newsletter",
                    "thread_id": "thread-newsletter",
                    "from_address": "a@newsletter.example.com",
                    "from_domain": "newsletter.example.com",
                    "subject": "Weekly digest",
                    "body_text": "Stuff happened.",
                }
            ]
        )
    )
    config_dir = tmp_path / "config" / "spork"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        f"""
        rules_path = "{rules_path}"
        db_path = "{tmp_path / "state.sqlite3"}"
        socket_path = "{tmp_path / "sporkd.sock"}"
        [provider]
        spec = "spork.core.providers.file.provider:FileProvider"
        [provider.kwargs]
        messages_path = "{messages_path}"
        actions_log_path = "{tmp_path / "actions.jsonl"}"
        [llm]
        spec = "spork.core.llm.clients.recorded:RecordedLLMClient"
        [llm.kwargs]
        responses_path = "{tmp_path / "responses.json"}"
        [alerts]
        spec = "spork.core.alerts.log:LoggingAlerter"
        """
    )
    (tmp_path / "responses.json").write_text("{{}}")
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "empty-config")

    result = _run("rules", "test", str(rules_path), env=env)

    assert result.returncode == 0
    assert "Loaded 1 rule" in result.stdout
    assert "Traceback" not in result.stderr
    assert '"matched_rule_id": "catch-newsletter"' in result.stdout
    assert '"message_id": "msg-newsletter"' in result.stdout
    assert not (tmp_path / "actions.jsonl").exists()

    validation = _run("rules", "validate", str(rules_path), "--json", env=env)
    assert validation.returncode == 0
    assert json.loads(validation.stdout)["safe_for_tier1"] is True

    rules_path.write_text(
        """
        [[rule]]
        id = "escalate-newsletter"
        when = { always = true }
        action = { type = "escalate" }
        """
    )
    unsafe = _run("rules", "validate", str(rules_path), "--json", env=env)
    assert unsafe.returncode == 1
    assert json.loads(unsafe.stdout)["safe_for_tier1"] is False


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
