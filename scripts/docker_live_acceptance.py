#!/usr/bin/env python3
"""Run bounded live Spork acceptance checks inside an isolated Docker network.

The runner deliberately keeps the daemon in Docker while the verifier stays on
the host. That lets the test disconnect only the daemon's network, continue to
inspect Fastmail, and compare remote mailbox state with the daemon's durable
SQLite audit log after recovery.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spork.core.providers.jmap.client import JmapClient, JmapError, _method_types, _query_types


@dataclass(frozen=True, slots=True)
class MailObservation:
    """Remote mailbox facts for one subject, with no message body retained."""

    message_id: str
    mailboxes: frozenset[str]


class AcceptanceFailure(Exception):
    """One bounded failure type for the release acceptance runner."""


def _load_dotenv(path: Path) -> None:
    """Load simple `.env` values, making the selected file authoritative."""
    if not path.is_file():
        raise AcceptanceFailure(f"environment file not found: {path}")
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key.strip()] = value


def _required(name: str) -> str:
    """Read one required non-secret-or-secret setting without printing its value."""
    value = os.environ.get(name)
    if not value:
        raise AcceptanceFailure(f"missing required setting: {name}")
    return value


def _run(command: list[str], *, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    """Run one external acceptance command with captured, bounded output."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AcceptanceFailure(f"command failed to run: {' '.join(command[:3])}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise AcceptanceFailure(f"command failed ({result.returncode}): {detail[-1000:]}")
    return result


def _write_configs(root: Path, *, account: str, rules_path: Path) -> dict[str, Path]:
    """Create disposable three-tier config files for one isolated daemon."""
    etc_xdg = root / "etc" / "xdg" / "spork"
    user_config = root / "config" / "spork"
    etc_spork = root / "etc" / "spork"
    for directory in (etc_xdg, user_config, etc_spork):
        directory.mkdir(parents=True, exist_ok=True)

    (etc_xdg / "config.toml").write_text(
        """[provider]
spec = "spork.core.providers.jmap.provider:JmapProvider"

[provider.kwargs]
host = "api.fastmail.com"
poll_interval_seconds = 5.0

[provider.secret_kwargs]
api_token = "JMAP_API_TOKEN"

[llm]
spec = "spork.core.llm.clients.recorded:RecordedLLMClient"

[llm.kwargs]
responses_path = "/config/responses.json"

[alerts]
spec = "spork.core.alerts.log:LoggingAlerter"
"""
    )
    (user_config / "config.toml").write_text(
        f"""rules_path = \"/config/rules.toml\"
db_path = \"/state/state.sqlite3\"
socket_path = \"/run/spork/sporkd.sock\"

[provider.kwargs]
allow_writes = true
expected_account_email = \"{account}\"

[tiering]
tier2_enabled = false
"""
    )
    (etc_spork / "enforced.toml").write_text(
        """[tiering]
default_unmatched_action = "ignore"
"""
    )
    (root / "secretspec.toml").write_text(
        """[project]
name = "spork-docker-acceptance"
revision = "1.0"

[profiles.default]
JMAP_API_TOKEN = { description = "Fastmail JMAP API token" }

[providers]
default = "env://"
"""
    )
    (root / "responses.json").write_text("{}\n")
    return {
        "system_config": etc_xdg / "config.toml",
        "user_config": user_config / "config.toml",
        "enforced": etc_spork / "enforced.toml",
        "secretspec": root / "secretspec.toml",
        "rules": rules_path,
    }


def _rules(path: Path, *, action_type: str) -> None:
    """Write a specific-sender rule plus a later catch-all sentinel rule."""
    path.write_text(
        f"""[[rule]]
id = "acceptance-specific-sender"
description = "The dedicated SMTP sender must win."
when = {{ from_in = [\"{_required("SMTP_SENDER")}\"] }}
action = {{ type = \"{action_type}\", mailbox = \"Archive\", reason = \"docker acceptance\" }}
enabled = true

[[rule]]
id = "acceptance-catch-all"
description = "This later rule detects first-match regressions."
when = {{}}
action = {{ type = \"move\", mailbox = \"Spam\", reason = \"catch-all sentinel\" }}
enabled = true
"""
    )


class DockerAcceptance:
    """Own one disposable daemon container, network, state directory, and report."""

    def __init__(self, args: argparse.Namespace, report: dict[str, Any]) -> None:
        self.args = args
        self.report = report
        self.container = f"spork-acceptance-{uuid.uuid4().hex[:10]}"
        self.network = f"spork-acceptance-net-{uuid.uuid4().hex[:10]}"
        self.root = Path(tempfile.mkdtemp(prefix="spork-acceptance-"))
        self.rules_path = self.root / "rules.toml"
        self.state_path = self.root / "state"
        self.run_path = self.root / "run"
        self.state_path.mkdir()
        self.run_path.mkdir()
        self.configs = _write_configs(self.root, account=args.account, rules_path=self.rules_path)
        _rules(self.rules_path, action_type="tag")

    def _docker(self, *args: str, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
        """Run Docker CLI commands used by the bounded lifecycle."""
        return _run(["docker", *args], timeout=timeout)

    def _mount_args(self) -> list[str]:
        """Return read-only config and durable state mounts for the daemon."""
        repo = Path.cwd().resolve()
        venv = Path(self.args.venv).resolve()
        packages = Path(self.args.packages).resolve()
        for path in (repo, venv, packages):
            if not path.exists():
                raise AcceptanceFailure(f"acceptance mount does not exist: {path}")
        return [
            "-v",
            f"{repo}:/workspace:ro",
            "-v",
            f"{self.configs['system_config']}:/etc/xdg/spork/config.toml:ro",
            "-v",
            f"{self.configs['user_config']}:/config/spork/config.toml:ro",
            "-v",
            f"{self.configs['enforced']}:/etc/spork/enforced.toml:ro",
            "-v",
            f"{self.configs['rules']}:/config/rules.toml:ro",
            "-v",
            f"{self.configs['secretspec']}:/config/secretspec.toml:ro",
            "-v",
            f"{self.root / 'responses.json'}:/config/responses.json:ro",
            "-v",
            f"{self.state_path}:/state:rw",
            "-v",
            f"{self.run_path}:/run:rw",
            "-v",
            f"{venv}:/venv:ro",
            "-v",
            f"{packages}:/venv-packages:ro",
        ]

    def start(self, *, create_network: bool = True) -> None:
        """Create the isolated network and start a non-root, read-only daemon."""
        if create_network:
            self._docker("network", "create", self.network)
        command = [
            "docker",
            "run",
            "-d",
            "--name",
            self.container,
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--network",
            self.network,
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev",
            "--env-file",
            str(self.args.env_file),
            "-e",
            "HOME=/tmp",
            "-e",
            "XDG_CONFIG_HOME=/config",
            "-e",
            "XDG_CONFIG_DIRS=/etc/xdg",
            "-e",
            "XDG_RUNTIME_DIR=/run",
            *self._mount_args(),
            "-w",
            "/workspace",
            self.args.image,
            "sh",
            "-lc",
            "PYTHONPATH=/venv-packages:/workspace/src:/venv/lib/python3.13/site-packages "
            "exec /venv/bin/python -m spork.daemon.main "
            "--secretspec /config/secretspec.toml --log-level INFO",
        ]
        _run(command, timeout=120.0)
        self._wait_status()

    def restart(self) -> None:
        """Restart the daemon while retaining its durable state and network."""
        self._docker("stop", self.container)
        self._docker("rm", self.container)
        self.start(create_network=False)

    def _exec(self, *args: str, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
        """Run a CLI command inside the daemon container without changing its state."""
        return self._docker(
            "exec",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-e",
            "PYTHONPATH=/venv-packages:/workspace/src:/venv/lib/python3.13/site-packages",
            self.container,
            "/venv/bin/python",
            "-m",
            "spork.cli.main",
            "--secretspec",
            "/config/secretspec.toml",
            *args,
            timeout=timeout,
        )

    def _wait_status(self) -> None:
        """Wait until the daemon's control socket answers status requests."""
        deadline = time.monotonic() + self.args.timeout
        while time.monotonic() < deadline:
            try:
                result = self._exec("status", timeout=10.0)
                if "paused: False" in result.stdout:
                    return
            except AcceptanceFailure:
                pass
            time.sleep(2)
        logs = self._docker("logs", self.container).stdout[-2000:]
        raise AcceptanceFailure(f"daemon did not become ready: {logs}")

    def stop(self) -> None:
        """Stop and remove the daemon and its isolated network."""
        self._docker("rm", "-f", self.container, timeout=30.0)
        self._docker("network", "rm", self.network, timeout=30.0)

    def record(self, name: str, passed: bool, detail: str) -> None:
        """Append one sanitized scenario result to the report."""
        self.report.setdefault("checks", []).append(
            {"name": name, "passed": passed, "detail": detail}
        )


def _send(subject: str, body: str, *, recipient: str) -> None:
    """Send one uniquely named acceptance message through the operator relay."""
    script = Path(__file__).with_name("send_test_email.py")
    result = _run(
        [
            sys.executable,
            str(script),
            "--from",
            _required("SMTP_SENDER"),
            "--to",
            recipient,
            "--subject",
            subject,
            "--body",
            body,
        ],
        timeout=60.0,
    )
    if "sent subject=" not in result.stdout:
        raise AcceptanceFailure("SMTP sender returned no delivery confirmation")


def _client(account: str) -> JmapClient:
    """Build a host-side read-only verifier for the expected Fastmail account."""
    return JmapClient(
        host="api.fastmail.com",
        api_token=_required("JMAP_API_TOKEN"),
        expected_account_email=account,
    )


def _observations(client: JmapClient, subject: str) -> list[MailObservation]:
    """Find matching messages across every mailbox without reading bodies."""
    client.connect()
    email_query, filter_condition_cls = _query_types()
    _, email_get, _, _ = _method_types()
    matches: dict[str, set[str]] = {}
    for mailbox_id, (name, _role) in client._mailboxes.items():
        response = client._request(
            email_query(filter=filter_condition_cls(in_mailbox=mailbox_id), limit=100)
        )
        ids = getattr(response, "ids", [])
        if not ids:
            continue
        result = client._request(
            email_get(
                ids=ids,
                properties=client._email_properties(),
                fetch_text_body_values=False,
                fetch_html_body_values=False,
            )
        )
        for raw in getattr(result, "data", []):
            if getattr(raw, "subject", "") == subject:
                message_id = getattr(raw, "id", None)
                if isinstance(message_id, str):
                    matches.setdefault(message_id, set()).add(name)
    return [
        MailObservation(message_id=message_id, mailboxes=frozenset(mailboxes))
        for message_id, mailboxes in matches.items()
    ]


def _wait_for_mail(
    client: JmapClient,
    subject: str,
    expected: frozenset[str],
    *,
    state_path: Path | None = None,
    timeout: float,
) -> MailObservation:
    """Wait for one subject to reach exactly the expected mailbox set."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches = _observations(client, subject)
        if len(matches) == 1 and matches[0].mailboxes == expected:
            if state_path is None or _audit_count(state_path, matches[0].message_id) == 1:
                return matches[0]
        time.sleep(5)
    matches = _observations(client, subject)
    audit = [
        _audit_count(state_path, item.message_id) if state_path is not None else None
        for item in matches
    ]
    raise AcceptanceFailure(
        f"mailbox/audit state did not converge for {subject!r}: {matches} {audit}"
    )


def _audit_count(state_path: Path, message_id: str) -> int:
    """Read the durable action count using SQLite's read-only URI mode."""
    import sqlite3

    uri = f"file:{state_path / 'state.sqlite3'}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM audit_log WHERE jmap_id = ? AND event = 'action_applied'",
                (message_id,),
            ).fetchone()[0]
        )


def _run_checks(test: DockerAcceptance, client: JmapClient) -> None:
    """Execute the bounded behavior checks in a safety-first order."""
    status = test._exec("status")
    test.record("daemon status", "paused: False" in status.stdout, status.stdout.strip())
    test._exec("pause")
    paused = test._exec("status")
    test._exec("resume")
    resumed = test._exec("status")
    test.record(
        "pause and resume",
        "paused: True" in paused.stdout and "paused: False" in resumed.stdout,
        f"pause={paused.stdout.strip()} resume={resumed.stdout.strip()}",
    )

    run_id = test.report["run_id"]
    recipient = test.args.account
    tag_subject = f"[spork-acceptance {run_id}] tag"
    _send(tag_subject, "Docker acceptance additive tag test.", recipient=recipient)
    tagged = _wait_for_mail(
        client,
        tag_subject,
        frozenset({"Inbox", "Archive"}),
        state_path=test.state_path,
        timeout=test.args.timeout,
    )
    test.record("tag action", True, f"{tagged.message_id}: Inbox + Archive")

    _rules(test.rules_path, action_type="move")
    test.restart()
    move_subject = f"[spork-acceptance {run_id}] first-match move"
    _send(move_subject, "Docker acceptance first-match move test.", recipient=recipient)
    moved = _wait_for_mail(
        client,
        move_subject,
        frozenset({"Archive"}),
        state_path=test.state_path,
        timeout=test.args.timeout,
    )
    test.record("move and first-match action", True, f"{moved.message_id}: Archive only")

    before_audit = _audit_count(test.state_path, moved.message_id)
    preview = test._exec("rules", "test", "/config/rules.toml", timeout=120.0)
    after_audit = _audit_count(test.state_path, moved.message_id)
    test.record(
        "live rules dry-run has no side effects",
        "no changes made" in preview.stdout and before_audit == after_audit,
        f"audit_count={after_audit}",
    )

    outage_subjects = [f"[spork-acceptance {run_id}] outage-{index}" for index in range(3)]
    test._docker("network", "disconnect", test.network, test.container)
    try:
        for subject in outage_subjects:
            _send(subject, "Docker acceptance network-recovery test.", recipient=recipient)
    finally:
        test._docker("network", "connect", test.network, test.container)
    outage_results = [
        _wait_for_mail(
            client,
            subject,
            frozenset({"Archive"}),
            state_path=test.state_path,
            timeout=test.args.timeout,
        )
        for subject in outage_subjects
    ]
    counts = [_audit_count(test.state_path, result.message_id) for result in outage_results]
    test.record(
        "network outage recovery",
        counts == [1, 1, 1],
        f"message_ids={[result.message_id for result in outage_results]} audit_counts={counts}",
    )

    test.restart()
    time.sleep(10)
    restart_count = _audit_count(test.state_path, moved.message_id)
    test.record(
        "restart idempotency",
        restart_count == 1,
        f"{moved.message_id}: audit_count={restart_count}",
    )


def main() -> int:
    """Run all checks, write a sanitized report, and return a release-test exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--account", required=True, help="Dedicated Fastmail acceptance account.")
    parser.add_argument(
        "--venv",
        default=os.environ.get("SPORK_ACCEPTANCE_VENV", "/tmp/opencode/live-test/venv"),
    )
    parser.add_argument(
        "--packages",
        default=os.environ.get("SPORK_ACCEPTANCE_PACKAGES", "/tmp/opencode/live-test/packages"),
    )
    parser.add_argument("--image", default="python:3.13-slim")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--output", type=Path, default=Path("/tmp/spork-acceptance-report.json"))
    args = parser.parse_args()

    report: dict[str, Any] = {
        "run_id": uuid.uuid4().hex[:12],
        "account": args.account,
        "checks": [],
    }
    test: DockerAcceptance | None = None
    try:
        _load_dotenv(args.env_file)
        _required("JMAP_API_TOKEN")
        _required("SMTP_SENDER")
        test = DockerAcceptance(args, report)
        test.start()
        verifier = _client(args.account)
        verifier.connect()
        _run_checks(test, verifier)
    except (AcceptanceFailure, JmapError, OSError, ValueError) as exc:
        report["error"] = str(exc)
    finally:
        if test is not None:
            try:
                test.stop()
            except AcceptanceFailure as exc:
                report["cleanup_error"] = str(exc)
        report["passed"] = not report.get("error") and all(
            check["passed"] for check in report["checks"]
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        if test is not None:
            shutil.rmtree(test.root, ignore_errors=True)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
