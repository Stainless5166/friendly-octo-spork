"""Acceptance tests for `spork reclassify <message-id>` (docs/DESIGN.md §7.4/§13).

Subprocess-based, matching test_status.py's pattern. Standalone —
none of these tests spawn a sporkd subprocess, proving reclassify
genuinely works without one (§7.4's WAL-mode reasoning).
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "reclassify", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _write_messages(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-newsletter",
                    "thread_id": "thread-1",
                    "from_address": "a@newsletter.example.com",
                    "from_domain": "newsletter.example.com",
                    "subject": "Weekly digest",
                    "body_text": "Stuff happened.",
                },
                {
                    "message_id": "msg-vip",
                    "thread_id": "thread-2",
                    "from_address": "boss@example.com",
                    "from_domain": "example.com",
                    "subject": "Urgent",
                    "body_text": "Need this today.",
                },
            ]
        )
    )


def _write_rules(path: Path) -> None:
    path.write_text(
        """
        [[rule]]
        id = "file-newsletter"
        when = { from_domain_in = ["newsletter.example.com"] }
        action = { type = "move", mailbox = "Reading" }

        [[rule]]
        id = "catch-all"
        when = { always = true }
        action = { type = "escalate" }
        """
    )


def _write_config(config_dir: Path, tmp_path: Path) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path)
    rules_path = tmp_path / "rules.toml"
    _write_rules(rules_path)
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
        """
    )
    return db_path


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg-config-home")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")
    return env


def _row(db_path: Path, jmap_id: str) -> tuple[object, ...] | None:
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT tier_reached, action_taken FROM processed_messages WHERE jmap_id = ?",
        (jmap_id,),
    ).fetchone()
    conn.close()
    return row


def test_reclassify_help_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "reclassify", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_reclassify_with_no_config_produces_a_clean_error(tmp_path: Path) -> None:
    env = _env(tmp_path)

    result = _run("msg-1", env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_reclassify_with_an_unknown_message_id_reports_a_clean_error(tmp_path: Path) -> None:
    env = _env(tmp_path)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)

    result = _run("no-such-message", env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "no-such-message" in result.stderr
    assert "Traceback" not in result.stderr


def test_reclassify_reruns_tier1_and_records_the_new_outcome(tmp_path: Path) -> None:
    env = _env(tmp_path)
    db_path = _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)

    result = _run("msg-newsletter", env=env)

    assert result.returncode == 0
    assert "move" in result.stdout.lower()
    assert _row(db_path, "msg-newsletter") == ("tier1", "move")


def test_reclassify_escalates_through_tier2_when_the_rule_says_so(tmp_path: Path) -> None:
    env = _env(tmp_path)
    db_path = _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)

    result = _run("msg-vip", env=env)

    assert result.returncode == 0
    assert _row(db_path, "msg-vip") == ("tier2", "ignore")


def test_reclassify_reprocesses_a_message_already_marked_processed(tmp_path: Path) -> None:
    """The whole point: forcing a message back through the pipeline
    even though it's already been acted on once."""
    env = _env(tmp_path)
    db_path = _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)

    first = _run("msg-newsletter", env=env)
    second = _run("msg-newsletter", env=env)

    assert first.returncode == 0
    assert second.returncode == 0
    assert _row(db_path, "msg-newsletter") == ("tier1", "move")
