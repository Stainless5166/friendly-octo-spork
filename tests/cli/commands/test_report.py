"""Acceptance tests for the bounded, read-only `spork report` command."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _write_config(
    config_dir: Path,
    tmp_path: Path,
    count: int = 3,
    action: str = "ignore",
    classification: bool = False,
) -> tuple[Path, Path]:
    config_dir.mkdir(parents=True, exist_ok=True)
    messages_path = tmp_path / "messages.json"
    messages_path.write_text(
        json.dumps(
            [
                {
                    "message_id": f"msg-{index}",
                    "thread_id": f"thread-{index}",
                    "from_address": f"sender{index}@example.com",
                    "from_domain": "example.com",
                    "subject": f"Message {index}",
                    "body_text": "A body",
                }
                for index in range(count)
            ]
        )
    )
    rules_path = tmp_path / "rules.toml"
    action_fields = f'type = "{action}"'
    if action == "move":
        action_fields += ', mailbox = "Reading"'
    classification_line = "classifications = { banking = 100 }" if classification else ""
    classification_config = (
        "[classification.mailboxes.banking]\n"
        'destination = "Banking and Finance"\n'
        "minimum_score = 70"
        if classification
        else ""
    )
    rules_path.write_text(
        f"""
        [[rule]]
        id = "example"
        when = {{ from_domain_in = ["example.com"] }}
        action = {{ {action_fields} }}
        {classification_line}
         """
    )
    db_path = tmp_path / "state.sqlite3"
    (config_dir / "config.toml").write_text(
        f"""
        rules_path = "{rules_path}"
        db_path = "{db_path}"

        [provider]
        spec = "spork.core.providers.file.provider:FileProvider"
        [provider.kwargs]
        messages_path = "{messages_path}"
        actions_log_path = "{tmp_path / "actions.jsonl"}"

        [llm]
        spec = "spork.core.llm.clients.recorded:RecordedLLMClient"
        [llm.kwargs]
        responses_path = "{tmp_path / "responses.json"}"

         [alerts]
         spec = "spork.core.alerts.log:LoggingAlerter"
         {classification_config}
         """
    )
    (tmp_path / "responses.json").write_text("{}")
    return db_path, messages_path


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "system")
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", "report", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def test_report_outputs_a_bounded_aggregate_without_creating_state(tmp_path: Path) -> None:
    db_path, _ = _write_config(tmp_path / "xdg" / "spork", tmp_path, count=3)

    result = _run(tmp_path, "--limit", "2")

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["sampled_messages"] == 2
    assert report["rule_actions"] == {"ignore": 2}
    assert not db_path.exists()


def test_report_can_write_an_explicit_non_sensitive_output_file(tmp_path: Path) -> None:
    _write_config(tmp_path / "xdg" / "spork", tmp_path)
    output_path = tmp_path / "report.json"

    result = _run(tmp_path, "--output", str(output_path))

    assert result.returncode == 0
    assert result.stdout == ""
    report = json.loads(output_path.read_text())
    assert report["sampled_messages"] == 3
    assert "Message 0" not in output_path.read_text()


def test_report_rejects_missing_configuration_without_traceback(tmp_path: Path) -> None:
    result = _run(tmp_path)

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_report_writes_a_sanitized_action_plan_without_side_effects(tmp_path: Path) -> None:
    db_path, messages_path = _write_config(tmp_path / "xdg" / "spork", tmp_path, action="move")
    plan_path = tmp_path / "planned-actions.jsonl"

    result = _run(tmp_path, "--limit", "2", "--actions-out", str(plan_path))

    assert result.returncode == 0
    assert json.loads(result.stdout)["rule_actions"] == {"move": 2}
    records = [json.loads(line) for line in plan_path.read_text().splitlines()]
    assert records == [
        {
            "action": {"mailbox": "Reading", "reason": None, "type": "move"},
            "matched_rule_id": "example",
            "message_id": "msg-0",
        },
        {
            "action": {"mailbox": "Reading", "reason": None, "type": "move"},
            "matched_rule_id": "example",
            "message_id": "msg-1",
        },
    ]
    assert "Message 0" not in plan_path.read_text()
    assert "A body" not in plan_path.read_text()
    assert not db_path.exists()
    assert not (messages_path.parent / "actions.jsonl").exists()


def test_report_plans_receipt_archiving_without_building_receipt_pipeline(tmp_path: Path) -> None:
    _write_config(tmp_path / "xdg" / "spork", tmp_path, action="archive_receipt")
    plan_path = tmp_path / "planned-actions.jsonl"

    result = _run(tmp_path, "--actions-out", str(plan_path))

    assert result.returncode == 0
    assert json.loads(result.stdout)["rule_actions"] == {"archive_receipt": 3}
    record = json.loads(plan_path.read_text().splitlines()[0])
    assert record["action"]["type"] == "archive_receipt"


def test_report_rejects_an_unwritable_action_plan_without_traceback(tmp_path: Path) -> None:
    _write_config(tmp_path / "xdg" / "spork", tmp_path)
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("occupied")

    result = _run(tmp_path, "--actions-out", str(parent_file / "plan.jsonl"))

    assert result.returncode == 1
    assert "Error: could not write action plan" in result.stderr
    assert "Traceback" not in result.stderr


def test_report_emits_composite_classification_decision(tmp_path: Path) -> None:
    _write_config(tmp_path / "xdg" / "spork", tmp_path, classification=True)
    plan_path = tmp_path / "planned-actions.jsonl"

    result = _run(tmp_path, "--actions-out", str(plan_path))

    assert result.returncode == 0
    record = json.loads(plan_path.read_text().splitlines()[0])
    assert record["classifications"] == [{"name": "banking", "score": 100.0}]
    assert record["decision"] == {"mailbox": "Banking and Finance", "tags": []}
