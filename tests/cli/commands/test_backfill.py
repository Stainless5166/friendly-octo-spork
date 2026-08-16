"""Acceptance tests for `spork backfill` (docs/ROADMAP.md M8).

Same subprocess/FileProvider/RecordedLLMClient convention as
test_reclassify.py — standalone, no sporkd subprocess, no live
network. Reuses process_message()/escalate_message() exactly like
reclassify does, over a BackfillProvider page instead of one
message-id.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from spork.core.state.db import StateDB


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "backfill", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _write_messages(path: Path, count: int) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-vip" if i == 0 else f"msg-newsletter-{i}",
                    "thread_id": f"thread-{i}",
                    "from_address": "boss@example.com" if i == 0 else "a@newsletter.example.com",
                    "from_domain": "example.com" if i == 0 else "newsletter.example.com",
                    "subject": "Urgent" if i == 0 else f"Weekly digest {i}",
                    "body_text": "Need this today." if i == 0 else "Stuff happened.",
                }
                for i in range(count)
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


def _write_config(config_dir: Path, tmp_path: Path, *, message_count: int = 3) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path, message_count)
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


def _processed_ids(db_path: Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT jmap_id FROM processed_messages").fetchall()
    conn.close()
    return {row[0] for row in rows}


def test_backfill_help_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "backfill", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_backfill_with_no_config_produces_a_clean_error(tmp_path: Path) -> None:
    env = _env(tmp_path)

    result = _run(env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_backfill_processes_every_message_through_tier1(tmp_path: Path) -> None:
    env = _env(tmp_path)
    db_path = _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, message_count=3)

    result = _run(env=env)

    assert result.returncode == 0
    assert _processed_ids(db_path) == {"msg-vip", "msg-newsletter-1", "msg-newsletter-2"}


def test_backfill_escalates_through_tier2_when_rules_say_so(tmp_path: Path) -> None:
    env = _env(tmp_path)
    db_path = _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, message_count=1)

    result = _run(env=env)

    assert result.returncode == 0
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT tier_reached, action_taken FROM processed_messages WHERE jmap_id = ?",
        ("msg-vip",),
    ).fetchone()
    conn.close()
    assert row == ("tier2", "ignore")


def test_backfill_respects_the_limit_option(tmp_path: Path) -> None:
    env = _env(tmp_path)
    db_path = _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, message_count=5)

    result = _run("--limit", "2", env=env)

    assert result.returncode == 0
    assert len(_processed_ids(db_path)) == 2


def test_backfill_writes_a_control_plane_audit_entry(tmp_path: Path) -> None:
    env = _env(tmp_path)
    db_path = _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, message_count=2)

    _run(env=env)

    with StateDB(db_path) as db:
        entries = [e for e in db.get_audit_entries() if e.event == "backfill_triggered"]

    assert len(entries) == 1
