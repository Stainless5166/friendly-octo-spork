"""Failure/edge-case tests for `spork reclassify <message-id>`.

Companion to test_reclassify.py's acceptance tests.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "reclassify", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _write_config(config_dir: Path, tmp_path: Path, *, daily_call_budget: int = 200) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    messages_path = tmp_path / "messages.json"
    messages_path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-vip",
                    "thread_id": "thread-1",
                    "from_address": "boss@example.com",
                    "from_domain": "example.com",
                    "subject": "Urgent",
                    "body_text": "Need this today.",
                }
            ]
        )
    )
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
        [[rule]]
        id = "catch-all"
        when = { always = true }
        action = { type = "escalate" }
        """
    )
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                "Urgent": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "ignore"},
                    "summary": "s",
                    "reasoning": "r",
                }
            }
        )
    )
    db_path = tmp_path / "state.sqlite3"
    (config_dir / "config.toml").write_text(
        f"""
        rules_path = "{rules_path}"
        db_path = "{db_path}"
        socket_path = "{tmp_path / "sporkd.sock"}"

        [provider]
        spec = "spork.core.providers.file.provider:FileProvider"
        [provider.kwargs]
        messages_path = "{messages_path}"
        actions_log_path = "{tmp_path / "actions.jsonl"}"

        [llm]
        spec = "spork.core.llm.clients.recorded:RecordedLLMClient"
        [llm.kwargs]
        responses_path = "{responses_path}"

        [alerts]
        spec = "spork.core.alerts.log:LoggingAlerter"

        [tiering]
        allowed_categories = ["needs_reply"]
        daily_call_budget = {daily_call_budget}
        """
    )
    return db_path


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg-config-home")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")
    return env


def _write_minimal_config(config_dir: Path, tmp_path: Path, *, llm_spec: str) -> None:
    """A config with one known-good message and a catch-all escalate
    rule, but a caller-supplied llm spec — for exercising a bad
    llm.spec cleanly, independent of _write_config's fixed-good one."""
    config_dir.mkdir(parents=True, exist_ok=True)
    messages_path = tmp_path / "messages.json"
    messages_path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "s",
                    "body_text": "b",
                }
            ]
        )
    )
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
        [[rule]]
        id = "catch-all"
        when = { always = true }
        action = { type = "escalate" }
        """
    )
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
        spec = "{llm_spec}"

        [alerts]
        spec = "spork.core.alerts.log:LoggingAlerter"
        """
    )


def test_reclassify_with_an_unloadable_provider_spec_reports_a_clean_error(tmp_path: Path) -> None:
    """load_provider() is called with no exception handling around it
    today — a bad provider.spec must still fail cleanly, same
    convention as every other load error in this CLI."""
    env = _env(tmp_path)
    config_dir = tmp_path / "xdg-config-home" / "spork"
    config_dir.mkdir(parents=True)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text("")
    (config_dir / "config.toml").write_text(
        f"""
        rules_path = "{rules_path}"
        db_path = "{tmp_path / "state.sqlite3"}"
        socket_path = "{tmp_path / "sporkd.sock"}"

        [provider]
        spec = "no.such.module:NoSuchClass"

        [llm]
        spec = "spork.core.llm.clients.recorded:RecordedLLMClient"
        [llm.kwargs]
        responses_path = "{tmp_path / "responses.json"}"

        [alerts]
        spec = "spork.core.alerts.log:LoggingAlerter"
        """
    )
    (tmp_path / "responses.json").write_text("{}")

    result = _run("msg-1", env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_reclassify_with_an_unloadable_rules_file_reports_a_clean_error(tmp_path: Path) -> None:
    env = _env(tmp_path)
    config_dir = tmp_path / "xdg-config-home" / "spork"
    config_dir.mkdir(parents=True)
    messages_path = tmp_path / "messages.json"
    messages_path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "s",
                    "body_text": "b",
                }
            ]
        )
    )
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text("this is not [ valid toml")
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
    (tmp_path / "responses.json").write_text("{}")

    result = _run("msg-1", env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_reclassify_with_an_unloadable_llm_spec_reports_a_clean_error_only_when_it_escalates(
    tmp_path: Path,
) -> None:
    """load_llm_client() is only called after Tier 1 escalates — a bad
    llm.spec must still fail cleanly at that point, not with a raw
    traceback."""
    env = _env(tmp_path)
    _write_minimal_config(
        tmp_path / "xdg-config-home" / "spork", tmp_path, llm_spec="no.such.module:NoSuchClass"
    )

    result = _run("msg-1", env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_reclassify_help_lists_the_message_id_argument() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "reclassify", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "message" in result.stdout.lower()


def test_reclassify_reports_budget_exhausted_rather_than_crashing(tmp_path: Path) -> None:
    """A rule that escalates, but the daily call budget is already at
    zero: a clear message, exit 0 — not an unhandled exception."""
    env = _env(tmp_path)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, daily_call_budget=0)

    result = _run("msg-vip", env=env)

    assert result.returncode == 0
    assert "budget" in result.stdout.lower()
    assert "Traceback" not in result.stderr


def test_reclassify_with_no_message_id_argument_is_a_usage_error() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "reclassify"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_reclassify_appears_in_top_level_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "reclassify" in result.stdout.lower()


def test_reclassify_works_while_a_real_sporkd_is_running(tmp_path: Path) -> None:
    """The real point of being standalone: reclassify against the same
    StateDB a running sporkd is using, concurrently, without either
    side failing (docs/DESIGN.md §7.4's WAL-mode reasoning)."""
    env = _env(tmp_path)
    db_path = _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)
    socket_path = tmp_path / "sporkd.sock"

    daemon = subprocess.Popen(
        [sys.executable, "-m", "spork.daemon.main"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not socket_path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert socket_path.exists(), "sporkd never created its control socket"

        result = _run("msg-vip", env=env)

        assert result.returncode == 0
        assert "Traceback" not in result.stderr
    finally:
        daemon.terminate()
        daemon.wait(timeout=5)

    assert db_path.exists()
