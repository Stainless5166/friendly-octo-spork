"""Acceptance tests for `spork pause`/`spork resume` (docs/DESIGN.md §6.2.2/§13).

Subprocess-based, matching test_status.py's pattern. Reuses `spork
status`'s own already-tested output to verify pause/resume actually
took effect, rather than re-deriving that verification some other way.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _write_config(config_dir: Path, tmp_path: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    messages_path = tmp_path / "messages.json"
    messages_path.write_text("[]")
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text("")
    # RecordedLLMClient with no recorded responses — real and
    # constructible (run_daemon() always constructs an LLMClient at
    # startup now), never actually called since messages_path is
    # empty.
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


def test_pause_and_resume_help_work() -> None:
    """Both commands' --help exit 0 and print usage."""
    for command in ("pause", "resume"):
        result = _run(command, "--help", env=dict(os.environ))
        assert result.returncode == 0
        assert "usage" in result.stdout.lower()


def test_pause_when_daemon_not_running_produces_a_clear_message(tmp_path: Path) -> None:
    """Same "daemon not running" convention as spork status."""
    env = _env(tmp_path)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)

    result = _run("pause", env=env)

    assert result.returncode == 1
    assert "not running" in (result.stdout + result.stderr).lower()
    assert "Traceback" not in result.stderr


def test_pause_then_resume_actually_toggles_daemon_state(tmp_path: Path) -> None:
    """End to end: pause a real sporkd, confirm via spork status, then
    resume it and confirm again."""
    env = _env(tmp_path)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)
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

        pause_result = _run("pause", env=env)
        status_after_pause = _run("status", env=env)
        resume_result = _run("resume", env=env)
        status_after_resume = _run("status", env=env)
    finally:
        daemon.terminate()
        daemon.wait(timeout=5)

    assert pause_result.returncode == 0
    assert "paused: True" in status_after_pause.stdout
    assert resume_result.returncode == 0
    assert "paused: False" in status_after_resume.stdout
