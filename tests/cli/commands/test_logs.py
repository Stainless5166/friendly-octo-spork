"""Acceptance tests for `spork logs` (docs/DESIGN.md §6.2.2/§13).

No daemon needed at all — audit_log is a StateDB table, readable
directly, the same reasoning that already lets rules/config file
edits work with the daemon stopped (§6.3). Subprocess-based, matching
the rest of tests/cli/commands/.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from spork.core.state.db import StateDB


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "logs", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _write_config(config_dir: Path, tmp_path: Path, db_path: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text("")
    (config_dir / "config.toml").write_text(
        f"""
        rules_path = "{rules_path}"
        db_path = "{db_path}"
        socket_path = "{tmp_path / "sporkd.sock"}"

        [provider]
        spec = "spork.core.providers.file.provider:FileProvider"
        [provider.kwargs]
        messages_path = "{tmp_path / "messages.json"}"
        actions_log_path = "{tmp_path / "actions.jsonl"}"

        [llm]
        spec = "unused:Unused"

        [alerts]
        spec = "spork.core.alerts.log:LoggingAlerter"
        """
    )
    (tmp_path / "messages.json").write_text("[]")


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg-config-home")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")
    return env


def test_logs_help_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "logs", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_logs_with_no_config_produces_a_clean_error(tmp_path: Path) -> None:
    env = _env(tmp_path)

    result = _run(env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_logs_prints_nothing_for_a_fresh_never_run_daemon(tmp_path: Path) -> None:
    """A fresh install, daemon never run: an empty log, not an error —
    StateDB creates its schema on first open regardless."""
    env = _env(tmp_path)
    db_path = tmp_path / "state.sqlite3"
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, db_path)

    result = _run(env=env)

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_logs_prints_entries_oldest_first(tmp_path: Path) -> None:
    env = _env(tmp_path)
    db_path = tmp_path / "state.sqlite3"
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, db_path)
    with StateDB(db_path) as db:
        db.write_audit_entry(ts="2026-08-12T09:00:00Z", jmap_id="msg-1", event="action_applied")
        db.write_audit_entry(
            ts="2026-08-12T10:00:00Z", jmap_id="msg-2", event="escalated_pending_tier2"
        )

    result = _run(env=env)

    assert result.returncode == 0
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 2
    assert "msg-1" in lines[0]
    assert "msg-2" in lines[1]


def test_logs_filters_by_message_id(tmp_path: Path) -> None:
    env = _env(tmp_path)
    db_path = tmp_path / "state.sqlite3"
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, db_path)
    with StateDB(db_path) as db:
        db.write_audit_entry(ts="2026-08-12T09:00:00Z", jmap_id="msg-1", event="action_applied")
        db.write_audit_entry(ts="2026-08-12T10:00:00Z", jmap_id="msg-2", event="action_applied")

    result = _run("--message-id", "msg-2", env=env)

    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1
    assert "msg-2" in lines[0]


def test_logs_filters_by_since(tmp_path: Path) -> None:
    env = _env(tmp_path)
    db_path = tmp_path / "state.sqlite3"
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, db_path)
    with StateDB(db_path) as db:
        db.write_audit_entry(ts="2026-08-12T09:00:00Z", jmap_id="msg-1", event="action_applied")
        db.write_audit_entry(ts="2026-08-12T10:00:00Z", jmap_id="msg-2", event="action_applied")

    result = _run("--since", "2026-08-12T09:30:00Z", env=env)

    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1
    assert "msg-2" in lines[0]


def test_logs_tail_shows_only_the_last_n_entries(tmp_path: Path) -> None:
    env = _env(tmp_path)
    db_path = tmp_path / "state.sqlite3"
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, db_path)
    with StateDB(db_path) as db:
        for i in range(5):
            db.write_audit_entry(
                ts=f"2026-08-12T0{i}:00:00Z", jmap_id=f"msg-{i}", event="action_applied"
            )

    result = _run("--tail", "2", env=env)

    lines = result.stdout.strip().splitlines()
    assert len(lines) == 2
    assert "msg-3" in lines[0]
    assert "msg-4" in lines[1]
