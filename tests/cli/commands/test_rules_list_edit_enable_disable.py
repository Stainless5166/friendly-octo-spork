"""Acceptance tests for `spork rules list/edit/enable/disable` (docs/DESIGN.md §6.2.2/§7.5/§13).

Subprocess-based, matching tests/cli/commands/test_status.py's
pattern. `edit` is exercised via a fake `$EDITOR` (a tiny Python
script, not an interactive editor) — the point of these tests is
spork's own validate-then-push-reload flow, not any particular
editor's behavior.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "rules", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _write_config(config_dir: Path, tmp_path: Path, *, rules_path: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    messages_path = tmp_path / "messages.json"
    messages_path.write_text("[]")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text("{}")
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
        """
    )


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg-config-home")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")
    return env


_TWO_RULES = """
[[rule]]
id = "vip-senders"
description = "Always escalate the boss"
when = { from_in = ["boss@example.com"] }
action = { type = "escalate", reason = "vip_sender", alert_immediately = true }

[[rule]]
id = "newsletters"
when = { from_domain_in = ["newsletter.example.com"] }
action = { type = "move", mailbox = "Reading" }
enabled = false
"""


def _fake_editor(tmp_path: Path, script: str) -> str:
    """Writes a tiny Python script standing in for $EDITOR and returns
    its path — real subprocess invocation, no live editor needed."""
    editor_path = tmp_path / "fake_editor.py"
    editor_path.write_text(script)
    return f"{sys.executable} {editor_path}"


def test_rules_list_prints_id_status_and_action_per_rule(tmp_path: Path) -> None:
    env = _env(tmp_path)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(_TWO_RULES)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, rules_path=rules_path)

    result = _run("list", env=env)

    assert result.returncode == 0
    assert "vip-senders" in result.stdout
    assert "enabled" in result.stdout
    assert "newsletters" in result.stdout
    assert "disabled" in result.stdout


def test_rules_list_with_no_rules_says_so(tmp_path: Path) -> None:
    env = _env(tmp_path)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text("")
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, rules_path=rules_path)

    result = _run("list", env=env)

    assert result.returncode == 0
    assert "no rules" in result.stdout.lower()


def test_rules_list_with_no_config_produces_a_clean_error(tmp_path: Path) -> None:
    env = _env(tmp_path)

    result = _run("list", env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_rules_edit_with_no_daemon_running_still_saves_and_says_so(tmp_path: Path) -> None:
    """A no-op $EDITOR (leaves the file untouched): the (still-valid)
    file re-validates fine, and with no sporkd reachable, the command
    says so plainly rather than erroring."""
    env = _env(tmp_path)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(_TWO_RULES)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, rules_path=rules_path)
    env["EDITOR"] = _fake_editor(tmp_path, "")  # does nothing

    result = _run("edit", env=env)

    assert result.returncode == 0
    assert "not running" in result.stdout.lower()


def test_rules_edit_rejects_an_invalid_save(tmp_path: Path) -> None:
    """$EDITOR that corrupts the file: spork rules edit validates on
    save and reports a clean error rather than accepting garbage."""
    env = _env(tmp_path)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(_TWO_RULES)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, rules_path=rules_path)
    corrupt_script = (
        f"import pathlib; pathlib.Path(r'{rules_path}').write_text('this is not [ valid toml')"
    )
    env["EDITOR"] = _fake_editor(tmp_path, corrupt_script)

    result = _run("edit", env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_rules_enable_flips_a_disabled_rule_and_rewrites_the_file(tmp_path: Path) -> None:
    env = _env(tmp_path)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(_TWO_RULES)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, rules_path=rules_path)

    result = _run("enable", "newsletters", env=env)

    assert result.returncode == 0
    list_result = _run("list", env=env)
    lines = [line for line in list_result.stdout.splitlines() if "newsletters" in line]
    assert len(lines) == 1
    assert "enabled" in lines[0]
    assert "disabled" not in lines[0]


def test_rules_disable_flips_an_enabled_rule(tmp_path: Path) -> None:
    env = _env(tmp_path)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(_TWO_RULES)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, rules_path=rules_path)

    result = _run("disable", "vip-senders", env=env)

    assert result.returncode == 0
    list_result = _run("list", env=env)
    lines = [line for line in list_result.stdout.splitlines() if "vip-senders" in line]
    assert len(lines) == 1
    assert "disabled" in lines[0]


def test_rules_enable_with_an_unknown_id_reports_a_clean_error(tmp_path: Path) -> None:
    env = _env(tmp_path)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(_TWO_RULES)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, rules_path=rules_path)

    result = _run("enable", "no-such-rule", env=env)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "no-such-rule" in result.stderr
    assert "Traceback" not in result.stderr
