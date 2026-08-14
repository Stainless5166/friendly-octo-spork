"""Acceptance tests for `spork status` (docs/DESIGN.md §6.2.2/§13).

Subprocess-based, matching tests/cli/commands/test_rules.py's
pattern: exercises the real installed console-script entry point.
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
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")  # empty, no real config
    return env


def test_status_help_works() -> None:
    """`spork status --help` exits 0 and prints usage, not a crash."""
    result = _run("status", "--help", env=dict(os.environ))

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_status_with_no_config_produces_a_clean_error(tmp_path: Path) -> None:
    """No config.toml anywhere: a clear ConfigLoadError message, never
    a raw traceback — same convention as sporkd itself."""
    result = _run("status", env=_env(tmp_path))

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_status_when_daemon_not_running_produces_a_clear_message(tmp_path: Path) -> None:
    """A valid config, but nothing listening on the socket: "daemon not
    running" messaging (docs/DESIGN.md §6.3), not a raw connection
    error or a silent no-op."""
    env = _env(tmp_path)
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path)

    result = _run("status", env=env)

    assert result.returncode == 1
    assert "not running" in (result.stdout + result.stderr).lower()
    assert "Traceback" not in result.stderr


def test_status_reports_real_daemon_state(tmp_path: Path) -> None:
    """End to end: a real sporkd subprocess, a real spork status
    subprocess talking to it over the real socket."""
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

        result = _run("status", env=env)

        assert result.returncode == 0
        assert "paused" in result.stdout.lower()
    finally:
        daemon.terminate()
        daemon.wait(timeout=5)
