"""Failure/edge-case tests for `spork backfill`.

Companion to test_backfill.py's acceptance tests.
"""

from __future__ import annotations

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
