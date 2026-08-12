"""Acceptance tests for spork.daemon.loop.run_daemon() (docs/DESIGN.md §6.2.1).

Exercised end to end against FileProvider + LoggingAlerter — a real
Provider/Alerter, no live JMAP session needed (docs/DESIGN.md §9.3),
proving the loop's own composition/threading logic works, not any
particular backend. Tier 1 only this round (§6.2.1's scope decision);
Tier 2 chaining is separate, tracked follow-up work.

Plain `asyncio.run()` inside ordinary sync test functions rather than
`pytest-asyncio` — stdlib is enough here, and this project has been
deliberately minimal about dependencies (docs/ROADMAP.md M7's tracing
item rejects a heavier dependency for the same reason).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest

from spork.core.config.schema import BackendSpec, SporkConfig
from spork.core.state.db import StateDB
from spork.daemon.loop import run_daemon


def _write_messages(path: Path) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-vip",
                    "thread_id": "thread-vip",
                    "from_address": "boss@example.com",
                    "from_domain": "example.com",
                    "subject": "Urgent",
                    "body_text": "Need this today.",
                },
                {
                    "message_id": "msg-plain",
                    "thread_id": "thread-plain",
                    "from_address": "newsletter@example.com",
                    "from_domain": "example.com",
                    "subject": "Weekly digest",
                    "body_text": "Stuff happened.",
                },
            ]
        )
    )


def _write_rules(path: Path) -> None:
    path.write_text(
        """
        [[rule]]
        id = "vip-senders"
        when = { from_in = ["boss@example.com"] }
        action = { type = "escalate", reason = "vip_sender", alert_immediately = true }

        [[rule]]
        id = "catch-all"
        when = { always = true }
        action = { type = "tag", mailbox = "Inbox" }
        """
    )


def _config(tmp_path: Path) -> SporkConfig:
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path)
    rules_path = tmp_path / "rules.toml"
    _write_rules(rules_path)

    return SporkConfig(
        provider=BackendSpec(
            spec="spork.core.providers.file.provider:FileProvider",
            kwargs={
                "messages_path": str(messages_path),
                "actions_log_path": str(tmp_path / "actions.jsonl"),
            },
        ),
        llm=BackendSpec(spec="unused:Unused"),  # never loaded — Tier 1 only this round
        alerts=BackendSpec(spec="spork.core.alerts.log:LoggingAlerter"),
        rules_path=rules_path,
        db_path=tmp_path / "state.sqlite3",
        socket_path=tmp_path / "sporkd.sock",  # unused this round, still required by callers
    )


async def _run_briefly(config: SporkConfig, *, settle_seconds: float = 0.2) -> None:
    """Runs run_daemon() for just long enough to process FileProvider's
    one fixed batch, then stops it cleanly."""
    stop_event = asyncio.Event()
    task = asyncio.create_task(run_daemon(config, stop_event=stop_event, idle_delay_seconds=0.02))
    await asyncio.sleep(settle_seconds)
    stop_event.set()
    await asyncio.wait_for(task, timeout=2)


def test_run_daemon_applies_a_matched_rules_action(tmp_path: Path) -> None:
    """The plain message matches catch-all and gets tagged — proving
    the loop actually runs messages through the real Tier 1 engine and
    a real ActionApplier (FileProvider's JSON-lines log)."""
    config = _config(tmp_path)

    asyncio.run(_run_briefly(config))

    actions_log = (tmp_path / "actions.jsonl").read_text().splitlines()
    entries = [json.loads(line) for line in actions_log]
    assert {"message_id": "msg-plain", "action_type": "tag", "mailbox": "Inbox"} in entries


def test_run_daemon_marks_processed_messages_in_state_db(tmp_path: Path) -> None:
    """Both messages end up recorded in StateDB — the idempotency
    guarantee (§11) holds through the real asyncio loop, not just
    process_message() called directly."""
    config = _config(tmp_path)

    asyncio.run(_run_briefly(config))

    with StateDB(config.db_path) as db:
        assert db.has_processed("msg-vip") is True
        assert db.has_processed("msg-plain") is True


def test_run_daemon_fires_a_vip_alert_through_pipeline_observer(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The VIP-sender rule's alert_immediately fires a real alert
    through the real LoggingAlerter loaded from config — end to end,
    not PipelineObserver constructed by hand in a test."""
    caplog.set_level(logging.INFO)
    config = _config(tmp_path)

    asyncio.run(_run_briefly(config))

    assert "vip_sender" in caplog.text


def test_run_daemon_stops_promptly_after_stop_event_is_set(tmp_path: Path) -> None:
    """run_daemon() actually returns once stop_event is set, rather
    than running forever — proven by awaiting it with a bounded
    timeout that would otherwise fail the test."""
    config = _config(tmp_path)

    async def _body() -> None:
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            run_daemon(config, stop_event=stop_event, idle_delay_seconds=0.02)
        )
        await asyncio.sleep(0.1)
        stop_event.set()
        await asyncio.wait_for(task, timeout=2)  # raises TimeoutError if it never stops

    asyncio.run(_body())
