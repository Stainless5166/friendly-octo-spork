"""Failure/edge-case tests for `spork backfill`.

Companion to test_backfill.py's acceptance tests.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tests.cli.commands.test_backfill import _env, _run, _write_config


def test_backfill_never_reprocesses_a_message_already_marked_processed(tmp_path: Path) -> None:
    """Running backfill twice acts on each message once, not twice —
    process_message()'s existing idempotency gate (docs/DESIGN.md §11)
    is what M8's 'never reprocess a message the live path already
    claimed' exit criterion actually rests on."""
    env = _env(tmp_path)
    db_path = _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, message_count=3)

    first = _run(env=env)
    second = _run(env=env)

    assert first.returncode == 0
    assert second.returncode == 0
    assert "0 Tier 1 actions" in second.stdout
    assert "0 Tier 2 verdicts" in second.stdout

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM processed_messages").fetchone()[0]
    conn.close()
    assert count == 3


def test_backfill_reports_a_clean_error_for_a_provider_without_the_capability(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "xdg-config-home" / "spork"
    config_dir.mkdir(parents=True, exist_ok=True)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        '[[rule]]\nid = "catch-all"\nwhen = { always = true }\naction = { type = "ignore" }\n'
    )
    (config_dir / "config.toml").write_text(
        f"""
        rules_path = "{rules_path}"
        db_path = "{tmp_path / "state.sqlite3"}"
        socket_path = "{tmp_path / "sporkd.sock"}"

        [provider]
        spec = "tests.support.no_backfill_provider:NoBackfillProvider"

        [llm]
        spec = "spork.core.llm.clients.recorded:RecordedLLMClient"
        [llm.kwargs]
        responses_path = "{tmp_path / "responses.json"}"

        [alerts]
        spec = "spork.core.alerts.log:LoggingAlerter"

        [tiering]
        """
    )
    (tmp_path / "responses.json").write_text("{}")
    env = _env(tmp_path)

    result = _run(env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "does not support backfill" in result.stderr
    assert "Traceback" not in result.stderr


def test_backfill_with_a_page_size_larger_than_the_limit_still_stops_at_the_limit(
    tmp_path: Path,
) -> None:
    env = _env(tmp_path)
    db_path = _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, message_count=5)

    result = _run("--limit", "1", "--page-size", "50", env=env)

    assert result.returncode == 0
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM processed_messages").fetchone()[0]
    conn.close()
    assert count == 1


def test_backfill_rejects_a_non_positive_limit(tmp_path: Path) -> None:
    """PR #20 review finding #4: --limit/--page-size had no positivity

    validation. --limit 0 previously ran successfully and reported "0
    messages processed" instead of being rejected - silently a no-op
    rather than a caught mistake."""
    env = _env(tmp_path)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, message_count=1)

    result = _run("--limit", "0", env=env)

    assert result.returncode != 0
    assert "Traceback" not in result.stderr


def test_backfill_rejects_a_non_positive_page_size(tmp_path: Path) -> None:
    env = _env(tmp_path)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, message_count=1)

    result = _run("--page-size", "0", env=env)

    assert result.returncode != 0
    assert "Traceback" not in result.stderr


def test_backfill_builds_tier2_provider_capabilities_once_per_run_not_per_message(
    tmp_path: Path,
) -> None:
    """PR #20 review finding #2: build_thread_history_reader()/

    build_mailbox_lister()/build_draft_creator() must be built once per
    backfill run, not once per escalated message — FileProvider's
    versions re-read the whole messages file from disk on every call,
    so calling them per-message would redo that work needlessly for
    every escalation.
    """
    messages_path = tmp_path / "messages.json"
    messages_path.write_text(
        json.dumps(
            [
                {
                    "message_id": f"msg-{i}",
                    "thread_id": f"thread-{i}",
                    "from_address": "boss@example.com",
                    "from_domain": "example.com",
                    "subject": f"Urgent {i}",
                    "body_text": "Need this today.",
                }
                for i in range(3)
            ]
        )
    )
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        '[[rule]]\nid = "catch-all"\nwhen = { always = true }\naction = { type = "escalate" }\n'
    )
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                f"Urgent {i}": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "ignore"},
                    "summary": "s",
                    "reasoning": "r",
                }
                for i in range(3)
            }
        )
    )
    counts_path = tmp_path / "capability_counts.json"
    config_dir = tmp_path / "xdg-config-home" / "spork"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text(
        f"""
        rules_path = "{rules_path}"
        db_path = "{tmp_path / "state.sqlite3"}"
        socket_path = "{tmp_path / "sporkd.sock"}"

        [provider]
        spec = "tests.support.counting_provider:CountingFileProvider"
        [provider.kwargs]
        messages_path = "{messages_path}"
        actions_log_path = "{tmp_path / "actions.jsonl"}"
        counts_path = "{counts_path}"

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
    env = _env(tmp_path)

    result = _run(env=env)

    assert result.returncode == 0
    assert "3 Tier 2 verdicts" in result.stdout
    counts = json.loads(counts_path.read_text())
    assert counts == {
        "build_thread_history_reader": 1,
        "build_mailbox_lister": 1,
        "build_draft_creator": 1,
    }


def test_backfill_quarantines_instead_of_crashing_on_an_out_of_set_category(
    tmp_path: Path,
) -> None:
    """Same fix as reclassify's: an out-of-set category is quarantined
    (counted, reported, StateDB-marked) instead of crashing the run."""
    messages_path = tmp_path / "messages.json"
    messages_path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
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
        '[[rule]]\nid = "catch-all"\nwhen = { always = true }\naction = { type = "escalate" }\n'
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
    config_dir = tmp_path / "xdg-config-home" / "spork"
    config_dir.mkdir(parents=True, exist_ok=True)
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
        responses_path = "{responses_path}"

        [alerts]
        spec = "spork.core.alerts.log:LoggingAlerter"

        [tiering]
        """
    )
    env = _env(tmp_path)

    result = _run(env=env)

    assert result.returncode == 0
    assert "1 quarantined" in result.stdout
    assert "Traceback" not in result.stderr
