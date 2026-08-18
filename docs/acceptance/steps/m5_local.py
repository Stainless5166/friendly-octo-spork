"""Local Behave bindings for M5's real IPC and CLI control surface."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from behave import given, then, when
from typer.testing import CliRunner

from spork.cli.main import app
from spork.core.ipc.client import send_request
from spork.core.ipc.server import IpcServer
from spork.core.rules.loader import load_rules
from spork.core.state.db import StateDB
from spork.daemon.loop import _build_ipc_handlers
from spork.daemon.state import DaemonState, RulesState

_runner = CliRunner()


def _write_local_config(root: Path) -> None:
    """Create a valid config whose provider and all state live under root."""
    rules = root / "rules.toml"
    rules.write_text(
        '[[rule]]\nid = "local"\nwhen = { always = true }\naction = { type = "ignore" }\n'
    )
    (root / "messages.json").write_text("[]")
    (root / "config.toml").write_text(
        f'''rules_path = "{rules}"
db_path = "{root / "state.sqlite3"}"
socket_path = "{root / "sporkd.sock"}"

[provider]
spec = "spork.core.providers.file.provider:FileProvider"
[provider.kwargs]
messages_path = "{root / "messages.json"}"
actions_log_path = "{root / "actions.jsonl"}"

[llm]
spec = "spork.core.llm.clients.recorded:RecordedLLMClient"
[llm.kwargs]
responses_path = "{root / "responses.json"}"

[alerts]
spec = "spork.core.alerts.log:LoggingAlerter"
'''
    )
    (root / "responses.json").write_text("{}")


def _cli(context: Any, *args: str):
    """Invoke the real top-level Typer app against this scenario's config."""
    return _runner.invoke(app, ["--config", str(context.root / "config.toml"), *args])


def _start_ipc(context: Any) -> None:
    """Serve the production daemon handlers until the scenario finishes."""
    context.daemon_state = DaemonState(started_at="2026-08-18T00:00:00+00:00")
    context.rules_state = RulesState(rules=load_rules(context.root / "rules.toml"))
    handlers = _build_ipc_handlers(
        context.daemon_state, context.rules_state, context.root / "rules.toml"
    )
    context.stop_event = asyncio.Event()

    async def serve() -> None:
        context.loop = asyncio.get_running_loop()
        await IpcServer(context.root / "sporkd.sock", handlers).serve(context.stop_event)

    def run() -> None:
        asyncio.run(serve())

    context.ipc_thread = threading.Thread(target=run, daemon=True)
    context.ipc_thread.start()
    for _ in range(100):
        if (context.root / "sporkd.sock").exists():
            return
        time.sleep(0.01)
    raise AssertionError("local IPC server did not create its socket")


def _stop_ipc(context: Any) -> None:
    """Stop the real server and join its worker before the next scenario."""
    if hasattr(context, "stop_event"):
        context.loop.call_soon_threadsafe(context.stop_event.set)
        context.ipc_thread.join(timeout=2)


@given("a local M5 daemon control socket and temporary FileProvider config")
def local_m5_daemon(context: Any) -> None:
    context.root = Path(tempfile.mkdtemp(prefix="spork-m5-"))
    _write_local_config(context.root)
    _start_ipc(context)


@when('the local M5 operator runs "spork status"')
def local_m5_status(context: Any) -> None:
    context.result = _cli(context, "status")


@then("the local M5 status command succeeds and reports a running daemon")
def local_m5_status_result(context: Any) -> None:
    assert context.result.exit_code == 0
    assert "started_at: 2026-08-18" in context.result.stdout
    _stop_ipc(context)


@when('the local M5 operator runs "spork pause" and then "spork resume"')
def local_m5_pause_resume(context: Any) -> None:
    context.pause_result = _cli(context, "pause")
    context.resume_result = _cli(context, "resume")


@then("the local M5 daemon state records pause and resume")
def local_m5_pause_resume_result(context: Any) -> None:
    assert context.pause_result.exit_code == 0
    assert context.resume_result.exit_code == 0
    assert context.daemon_state.paused is False
    events = [event.event for event in context.daemon_state.pending_control_plane_events]
    assert events == ["daemon_paused", "daemon_resumed"]
    _stop_ipc(context)


@when("the local M5 operator reloads a valid rules edit")
def local_m5_reload_valid(context: Any) -> None:
    with (context.root / "rules.toml").open("a") as rules:
        rules.write(
            '\n[[rule]]\nid = "second"\nwhen = { always = true }\naction = { type = "ignore" }\n'
        )
    context.reload_result = send_request(context.root / "sporkd.sock", "reload")


@then("the local M5 reload reports the new rule count")
def local_m5_reload_count(context: Any) -> None:
    assert context.reload_result.ok
    assert context.reload_result.data["rule_count"] == 2


@when("the local M5 operator reloads malformed rules")
def local_m5_reload_invalid(context: Any) -> None:
    context.valid_rules = context.rules_state.rules
    (context.root / "rules.toml").write_text("not valid = [ toml")
    context.bad_reload = send_request(context.root / "sporkd.sock", "reload")


@then("the local M5 reload fails without changing the last valid rules")
def local_m5_reload_failure(context: Any) -> None:
    assert not context.bad_reload.ok
    assert context.rules_state.rules == context.valid_rules
    _stop_ipc(context)


@given("a valid local M5 user config and a temporary editor")
def local_m5_config(context: Any) -> None:
    context.root = Path(tempfile.mkdtemp(prefix="spork-m5-config-"))
    _write_local_config(context.root)
    editor = context.root / "editor.py"
    editor.write_text("# intentionally leaves the valid config unchanged\n")
    context.editor = f"{sys.executable} {editor}"


@when('the local M5 operator runs "spork config edit"')
def local_m5_config_edit(context: Any) -> None:
    context.result = _runner.invoke(
        app,
        ["--config", str(context.root / "config.toml"), "config", "edit"],
        env={"EDITOR": context.editor},
    )


@then("the local M5 config command succeeds and instructs a daemon restart")
def local_m5_config_result(context: Any) -> None:
    assert context.result.exit_code == 0
    assert "Restart sporkd to apply" in context.result.stdout


@given("a local M5 config with a control-plane audit entry")
def local_m5_audit(context: Any) -> None:
    context.root = Path(tempfile.mkdtemp(prefix="spork-m5-logs-"))
    _write_local_config(context.root)
    with StateDB(context.root / "state.sqlite3") as db:
        db.write_control_plane_audit_entry(
            ts="2026-08-18T00:00:00+00:00",
            event="daemon_paused",
            detail_json=json.dumps({"local": True}),
        )


@when('the local M5 operator runs "spork logs"')
def local_m5_logs(context: Any) -> None:
    context.result = _cli(context, "logs")


@then("the local M5 logs command displays the audit event without a traceback")
def local_m5_logs_result(context: Any) -> None:
    assert context.result.exit_code == 0
    assert "daemon_paused" in context.result.stdout
    assert '"local": true' in context.result.stdout
    assert "Traceback" not in context.result.output
