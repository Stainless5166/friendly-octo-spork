"""Local Behave bindings for M6's dependency-free systemd boundaries."""

from __future__ import annotations

import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from behave import given, then, when
from typer.testing import CliRunner

from spork.cli.main import app
from spork.core.systemd.install import install_service
from spork.core.systemd.notify import notify
from spork.core.systemd.template import UNIT_FILE_CONTENT

_runner = CliRunner()


@when("the local M6 operator inspects the service unit template")
def local_m6_inspect_unit(context: Any) -> None:
    context.unit = UNIT_FILE_CONTENT


@then("the local M6 unit is notify-based and contains no secret values")
def local_m6_unit_result(context: Any) -> None:
    assert "Type=notify" in context.unit
    assert "Restart=on-failure" in context.unit
    assert "JMAP_API_TOKEN" not in context.unit
    assert "ANTHROPIC_API_KEY" not in context.unit
    assert "Bearer" not in context.unit


@when("the local M6 operator installs a unit with a fake systemctl runner")
def local_m6_install(context: Any) -> None:
    context.root = Path(tempfile.mkdtemp(prefix="spork-m6-install-"))
    context.calls = []

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        context.calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    context.unit_path = install_service(
        instance="local", unit_path=context.root / "sporkd@.service", runner=runner
    )


@then("the local M6 unit is written and systemctl receives reload and enable calls")
def local_m6_install_result(context: Any) -> None:
    assert context.unit_path.read_text() == UNIT_FILE_CONTENT
    assert context.calls == [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", "sporkd@local"],
    ]


@given("a local M6 doctor environment with an invalid config")
def local_m6_doctor_environment(context: Any) -> None:
    context.root = Path(tempfile.mkdtemp(prefix="spork-m6-doctor-"))
    context.config_path = context.root / "config.toml"
    context.config_path.write_text("this is not [ valid toml")


@when('the local M6 operator runs "spork doctor"')
def local_m6_doctor(context: Any) -> None:
    context.result = _runner.invoke(app, ["--config", str(context.config_path), "doctor"])


@then("the local M6 doctor reports every check without a traceback")
def local_m6_doctor_result(context: Any) -> None:
    output = context.result.output
    assert context.result.exit_code == 1
    for name in (
        "secrets",
        "config",
        "provider",
        "LLM client",
        "alerter",
        "rules",
        "local classifier",
        "JMAP connectivity",
        "systemd unit",
    ):
        assert name in output
    assert "Traceback" not in output


@when("the local M6 operator listens on a temporary notify socket")
def local_m6_notify(context: Any) -> None:
    context.socket_path = Path(tempfile.mktemp(prefix="spork-m6-notify-", dir="/tmp"))
    context.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    context.sock.bind(str(context.socket_path))
    assert notify("READY=1", socket_path=str(context.socket_path))
    context.datagram = context.sock.recv(64).decode()
    context.sock.close()
    context.socket_path.unlink(missing_ok=True)


@then("the local M6 readiness datagram is READY=1")
def local_m6_notify_result(context: Any) -> None:
    assert context.datagram == "READY=1"
