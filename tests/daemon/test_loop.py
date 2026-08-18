"""Acceptance tests for spork.daemon.loop.run_daemon() (docs/DESIGN.md §6.2.1).

Exercised end to end against FileProvider + LoggingAlerter +
RecordedLLMClient — real Provider/Alerter/LLMClient backends, no live
JMAP or Anthropic session needed (docs/DESIGN.md §9.3, §10.5),
proving the loop's own composition/threading logic works, not any
particular backend. Tier 1+2: §6.2.1's "Tier 1 only" scope decision is
resolved — an escalating message now flows straight into
process_tier2_message() in the same poll cycle.

Plain `asyncio.run()` inside ordinary sync test functions rather than
`pytest-asyncio` — stdlib is enough here, and this project has been
deliberately minimal about dependencies (docs/ROADMAP.md M7's tracing
item rejects a heavier dependency for the same reason).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from pathlib import Path

import pytest

from spork.core.config.schema import (
    BackendSpec,
    LLMRecordingConfig,
    ReceiptArchiveConfig,
    SporkConfig,
    TieringConfig,
)
from spork.core.secrets import Secrets
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


def _write_responses(path: Path) -> None:
    """One recorded verdict, keyed by the VIP message's subject ("Urgent")
    — the only message either test rules.toml file escalates, so this
    is the only response Tier 2 ever needs to look up. `suggested_action`
    is "ignore" (mailbox=None) specifically to sidestep §10.2's
    available_mailboxes validation — this test suite is about the loop's
    own wiring, not verdict-validation edge cases (those live in
    tests/core/llm/)."""
    path.write_text(
        json.dumps(
            {
                "Urgent": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "ignore"},
                    "summary": "Needs a reply today.",
                    "reasoning": "Sender is a VIP and the tone is urgent.",
                }
            }
        )
    )


def _config(tmp_path: Path) -> SporkConfig:
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path)
    rules_path = tmp_path / "rules.toml"
    _write_rules(rules_path)
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path)

    return SporkConfig(
        provider=BackendSpec(
            spec="spork.core.providers.file.provider:FileProvider",
            kwargs={
                "messages_path": str(messages_path),
                "actions_log_path": str(tmp_path / "actions.jsonl"),
            },
        ),
        llm=BackendSpec(
            spec="spork.core.llm.clients.recorded:RecordedLLMClient",
            kwargs={"responses_path": str(responses_path)},
        ),
        alerts=BackendSpec(spec="spork.core.alerts.log:LoggingAlerter"),
        rules_path=rules_path,
        db_path=tmp_path / "state.sqlite3",
        socket_path=tmp_path / "sporkd.sock",  # unused this round, still required by callers
        tiering=TieringConfig(allowed_categories=["needs_reply"]),
    )


async def _run_briefly(
    config: SporkConfig, *, settle_seconds: float = 0.5, **kwargs: object
) -> None:
    """Runs run_daemon() for just long enough to process FileProvider's
    one fixed batch, then stops it cleanly. Extra kwargs pass straight
    through to run_daemon() (e.g. notify_fn)."""
    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_daemon(config, stop_event=stop_event, idle_delay_seconds=0.02, **kwargs)
    )
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


def test_run_daemon_runs_an_escalated_message_through_tier2(tmp_path: Path) -> None:
    """The VIP-sender rule escalates msg-vip; the loop now carries it
    straight into process_tier2_message() in the same poll cycle
    (docs/DESIGN.md §6.2.1) — proven by the row ending up tier_reached
    == "tier2" with the recorded verdict's action, not stuck at Tier
    1's placeholder "escalate" row. Raw sqlite3 introspection, same
    pattern as tests/core/pipeline/tier2/test_integration_with_tier1.py's
    _row() helper — StateDB itself has no public "get one row" accessor."""
    config = _config(tmp_path)

    asyncio.run(_run_briefly(config))

    conn = sqlite3.connect(str(config.db_path))
    row = conn.execute(
        "SELECT tier_reached, action_taken FROM processed_messages WHERE jmap_id = ?",
        ("msg-vip",),
    ).fetchone()
    conn.close()
    assert row == ("tier2", "ignore")


def test_run_daemon_observe_mode_never_enters_tier2(tmp_path: Path, monkeypatch) -> None:
    """Observe mode must not call Tier 2, even when Tier 1 escalates."""
    config = _config(tmp_path)

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("observe mode entered Tier 2")

    monkeypatch.setattr("spork.daemon.loop.escalate_message_or_quarantine", fail_if_called)
    asyncio.run(_run_briefly(config, observe=True))

    assert not (tmp_path / "actions.jsonl").exists()
    assert not (tmp_path / "drafts.jsonl").exists()


def test_run_daemon_observe_mode_does_not_build_llm_or_write_production_state(
    tmp_path: Path, monkeypatch
) -> None:
    """Observe mode is an isolated read-only run, not normal processing with
    the action applier swapped for a no-op."""
    config = _config(tmp_path)

    def fail_if_built(*args: object, **kwargs: object) -> None:
        raise AssertionError("observe mode built an LLM client")

    monkeypatch.setattr("spork.daemon.loop.build_llm_client", fail_if_built)

    asyncio.run(_run_briefly(config, observe=True))

    assert not config.db_path.exists()


def test_run_daemon_injects_mapped_secrets_and_records_the_live_llm_path(tmp_path: Path) -> None:
    config = _config(tmp_path)
    messages_path = Path(config.provider.kwargs["messages_path"])
    responses_path = Path(config.llm.kwargs["responses_path"])
    corpus_path = tmp_path / "corpus" / "live.jsonl"
    config = config.model_copy(
        update={
            "provider": config.provider.model_copy(
                update={
                    "kwargs": {"actions_log_path": config.provider.kwargs["actions_log_path"]},
                    "secret_kwargs": {"messages_path": "MESSAGES_PATH"},
                }
            ),
            "llm": config.llm.model_copy(
                update={
                    "kwargs": {},
                    "secret_kwargs": {"responses_path": "RESPONSES_PATH"},
                }
            ),
            "llm_recording": LLMRecordingConfig(corpus_path=corpus_path),
        }
    )

    asyncio.run(
        _run_briefly(
            config,
            secrets=Secrets(
                {
                    "MESSAGES_PATH": str(messages_path),
                    "RESPONSES_PATH": str(responses_path),
                }
            ),
        )
    )

    entries = [json.loads(line) for line in corpus_path.read_text().splitlines()]
    assert [entry["subject"] for entry in entries] == ["Urgent"]


def _write_two_escalating_messages(path: Path) -> None:
    """Two messages, both destined to escalate (docs/DESIGN.md §12.3's
    "fires only once even across multiple escalations" acceptance
    test needs a second escalation in the same run — one VIP sender
    isn't enough to prove the daemon-level alert doesn't fire twice)."""
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-vip-1",
                    "thread_id": "thread-vip-1",
                    "from_address": "boss@example.com",
                    "from_domain": "example.com",
                    "subject": "Urgent one",
                    "body_text": "Need this today.",
                },
                {
                    "message_id": "msg-vip-2",
                    "thread_id": "thread-vip-2",
                    "from_address": "boss@example.com",
                    "from_domain": "example.com",
                    "subject": "Urgent two",
                    "body_text": "Need this too.",
                },
            ]
        )
    )


def _write_escalate_all_rules(path: Path) -> None:
    path.write_text(
        """
        [[rule]]
        id = "vip-senders"
        when = { from_in = ["boss@example.com"] }
        action = { type = "escalate", reason = "vip_sender", alert_immediately = true }
        """
    )


def _config_with_exhausted_budget(tmp_path: Path) -> SporkConfig:
    """Two escalating messages against a `daily_call_budget=0` — every
    Tier 2 attempt lands on the budget_exhausted branch without ever
    calling the (deliberately misconfigured, should-never-be-reached)
    LLM client, same "budget check happens before any LLM call" fact
    §10.4/§10.7 already rely on."""
    messages_path = tmp_path / "messages.json"
    _write_two_escalating_messages(messages_path)
    rules_path = tmp_path / "rules.toml"
    _write_escalate_all_rules(rules_path)
    responses_path = tmp_path / "responses.json"
    responses_path.write_text("{}")  # never consulted: budget_exhausted skips CallLLMAugment

    return SporkConfig(
        provider=BackendSpec(
            spec="spork.core.providers.file.provider:FileProvider",
            kwargs={
                "messages_path": str(messages_path),
                "actions_log_path": str(tmp_path / "actions.jsonl"),
            },
        ),
        llm=BackendSpec(
            spec="spork.core.llm.clients.recorded:RecordedLLMClient",
            kwargs={"responses_path": str(responses_path)},
        ),
        alerts=BackendSpec(spec="spork.core.alerts.log:LoggingAlerter"),
        rules_path=rules_path,
        db_path=tmp_path / "state.sqlite3",
        socket_path=tmp_path / "sporkd.sock",
        tiering=TieringConfig(allowed_categories=["needs_reply"], daily_call_budget=0),
    )


def test_run_daemon_fires_a_daemon_level_alert_when_the_daily_budget_is_exhausted(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A daemon-health alert distinct from RecordBudgetExhaustedFilter's
    existing per-message "Tier 2 skipped" alert (docs/DESIGN.md §12.3)
    fires once the daily call budget is already gone."""
    caplog.set_level(logging.INFO)
    config = _config_with_exhausted_budget(tmp_path)

    asyncio.run(_run_briefly(config))

    assert "Daily LLM budget exhausted" in caplog.text


def test_run_daemon_fires_the_daemon_level_budget_alert_only_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Both fixture messages escalate onto an already-exhausted budget
    in the same run, but the one-shot-per-day daemon alert fires only
    once — unlike the per-message RecordBudgetExhaustedFilter alert,
    which fires for each of them.

    Counts actual deliveries (records from LoggingAlerter's own
    logger), not raw substring occurrences in caplog.text — a single
    PipelineObserver.alert() call legitimately logs the same title
    twice (once via trace(), once via the delivery itself), so a
    plain text.count() would overcount even one real alert."""
    caplog.set_level(logging.INFO)
    config = _config_with_exhausted_budget(tmp_path)

    asyncio.run(_run_briefly(config))

    deliveries = [
        r
        for r in caplog.records
        if r.name == "spork.core.alerts.log" and "Daily LLM budget exhausted" in r.getMessage()
    ]
    assert len(deliveries) == 1


def test_run_daemon_does_not_fire_the_daemon_level_budget_alert_when_budget_remains(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The ordinary VIP-escalation config (default daily_call_budget)
    never trips the new daemon-health alert — it's specific to
    exhaustion, not a side effect of any escalation."""
    caplog.set_level(logging.INFO)
    config = _config(tmp_path)

    asyncio.run(_run_briefly(config))

    assert "Daily LLM budget exhausted" not in caplog.text


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


def test_run_daemon_signals_readiness_via_notify_fn(tmp_path: Path) -> None:
    """docs/DESIGN.md §14: once the daemon has finished composing its
    provider/rules/LLM client/alerter and is about to enter its
    message loop, it calls notify_fn("READY=1") — proven here via an
    injected stub rather than a real $NOTIFY_SOCKET (spork.core.systemd.notify
    already covers the wire protocol itself in isolation)."""
    config = _config(tmp_path)
    calls: list[str] = []

    asyncio.run(_run_briefly(config, notify_fn=calls.append))

    assert calls == ["READY=1"]


def test_run_daemon_signals_readiness_exactly_once(tmp_path: Path) -> None:
    """Not once per poll iteration — README/PipelineObserver-consuming
    documentation only needs one "I'm up" per process lifetime."""
    config = _config(tmp_path)
    calls: list[str] = []

    asyncio.run(_run_briefly(config, notify_fn=calls.append, settle_seconds=0.3))

    assert calls.count("READY=1") == 1


def _receipt_config(tmp_path: Path) -> SporkConfig:
    """A self-contained config for the receipt-archiving tests below --
    one known-sender receipt message, one archive_receipt rule, a
    RecordedReceiptExtractionClient (never actually called for a known
    sender, but still required config)."""
    messages_path = tmp_path / "messages.json"
    messages_path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-receipt",
                    "thread_id": "thread-receipt",
                    "from_address": "billing@acmecloud.com",
                    "from_domain": "acmecloud.com",
                    "subject": "Your receipt",
                    "body_text": "Thanks for your payment.",
                    "headers": {"Date": "Sat, 01 Aug 2026 00:00:00 +0000"},
                }
            ]
        )
    )
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
        [[rule]]
        id = "receipts"
        when = { from_domain_in = ["acmecloud.com"] }
        action = { type = "archive_receipt" }
        """
    )
    extractions_path = tmp_path / "extractions.json"
    extractions_path.write_text("{}")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text("{}")

    return SporkConfig(
        provider=BackendSpec(
            spec="spork.core.providers.file.provider:FileProvider",
            kwargs={
                "messages_path": str(messages_path),
                "actions_log_path": str(tmp_path / "actions.jsonl"),
            },
        ),
        llm=BackendSpec(
            spec="spork.core.llm.clients.recorded:RecordedLLMClient",
            kwargs={"responses_path": str(responses_path)},
        ),
        alerts=BackendSpec(spec="spork.core.alerts.log:LoggingAlerter"),
        rules_path=rules_path,
        db_path=tmp_path / "state.sqlite3",
        socket_path=tmp_path / "sporkd.sock",
        receipt_archive=ReceiptArchiveConfig(
            output_dir=tmp_path / "receipts",
            extraction=BackendSpec(
                spec="spork.core.receipts.llm:RecordedReceiptExtractionClient",
                kwargs={"responses_path": str(extractions_path)},
            ),
        ),
    )


def test_run_daemon_archives_a_matched_receipt_message(tmp_path: Path) -> None:
    """A known sender (seeded directly into StateDB before the loop
    starts) is archived end to end through the real asyncio loop --
    the same collaborators build_receipt_archive_components() composes
    from a real config, not hand-wired in the test."""
    config = _receipt_config(tmp_path)
    with StateDB(config.db_path) as db:
        db.learn_known_sender(
            "acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
        )

    asyncio.run(_run_briefly(config))

    with StateDB(config.db_path) as db:
        assert db.has_processed("msg-receipt") is True
    assert config.receipt_archive is not None
    saved = list(config.receipt_archive.output_dir.glob("*.pdf"))
    assert len(saved) == 1
    keywords_log = json.loads((tmp_path / "keywords.jsonl").read_text().splitlines()[0])
    assert keywords_log["keywords"][:2] == ["receipt", "company:Acme Cloud"]


def test_run_daemon_observe_mode_does_not_archive_or_tag_receipts(tmp_path: Path) -> None:
    """--observe's contract ('process and audit messages without
    changing mail or creating drafts') covers archive_receipt too: no
    PDF written, no keyword applied, and no production state is changed."""
    config = _receipt_config(tmp_path)
    with StateDB(config.db_path) as db:
        db.learn_known_sender(
            "acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
        )

    asyncio.run(_run_briefly(config, observe=True))

    with StateDB(config.db_path) as db:
        assert db.has_processed("msg-receipt") is False
    assert config.receipt_archive is not None
    assert not config.receipt_archive.output_dir.exists()
    assert not (tmp_path / "keywords.jsonl").exists()
