"""Failure/edge-case tests for `spork rules list/edit/enable/disable`.

Companion to test_rules_list_edit_enable_disable.py's acceptance
tests. Covers `_push_reload()`'s two branches its sibling file's
tests don't reach: a real running sporkd actually accepting a reload
(end to end, subprocess), and sporkd rejecting one (a bare IpcServer
standing in for a real daemon — no mocking of the IPC boundary, just a
different, real handler behind it).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from spork.core.ipc.server import IpcServer


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


def test_rules_enable_reports_success_against_a_real_running_sporkd(tmp_path: Path) -> None:
    """End to end: a real sporkd subprocess, a real spork rules enable
    subprocess talking to it over the real socket — the "sporkd
    reloaded" branch _push_reload's other tests don't reach."""
    env = _env(tmp_path)
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
        [[rule]]
        id = "catch-all"
        when = { always = true }
        action = { type = "tag", mailbox = "Inbox" }
        enabled = false
        """
    )
    _write_config(tmp_path / "xdg-config-home" / "spork", tmp_path, rules_path=rules_path)
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

        result = _run("enable", "catch-all", env=env)

        assert result.returncode == 0
        assert "reloaded" in result.stdout.lower()
    finally:
        daemon.terminate()
        daemon.wait(timeout=5)


def test_push_reload_reports_a_warning_when_sporkd_rejects_the_reload(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A running IpcServer whose "reload" handler reports failure (a
    stand-in for a daemon-side RulesLoadError) — _push_reload() prints
    a warning, not a silent success."""
    from spork.cli.commands.rules import _push_reload

    socket_path = tmp_path / "fake-sporkd.sock"

    def _failing_reload(params: dict[str, object]) -> dict[str, object]:
        raise ValueError("simulated: bad rules.toml on the daemon side")

    server = IpcServer(socket_path, handlers={"reload": _failing_reload})

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(server.serve(stop_event))
        await asyncio.sleep(0.1)

        await asyncio.to_thread(_push_reload, socket_path)

        stop_event.set()
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(_body())

    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    assert "simulated: bad rules.toml" in captured.err


def test_push_reload_with_no_socket_path_falls_back_to_resolve_socket_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """socket_path=None (as config.socket_path can be before
    load_config() resolves it) falls back to resolve_socket_path() —
    same defensive pattern run_daemon() already uses."""
    from spork.cli.commands.rules import _push_reload

    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    _push_reload(None)

    captured = capsys.readouterr()
    assert "not running" in captured.out.lower()
