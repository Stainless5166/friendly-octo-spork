"""Integration test: a Tier 1 escalation followed by a Tier 2 run
(docs/DESIGN.md §10.7's closing claim).

§10.7 explicitly justifies *not* giving the Tier 2 pipeline its own
idempotency gate by claiming `MarkProcessedFilter`'s upsert simply
overwrites Tier 1's `processed_messages` row (`tier_reached="tier1"`
-> `"tier2"`) once something calls `process_tier2_message()` for the
right message. That claim was never actually exercised end to end
until this test — every other test in this suite exercises Tier 1 and
Tier 2 against a fresh StateDB, never the same message through both in
sequence.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.context.clients.null import NullContextProvider
from spork.core.llm.clients.recorded import RecordedLLMClient
from spork.core.models import NormalizedMessage
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2 import process_tier2_message
from spork.core.rules.schema import Action
from spork.core.state.db import StateDB


class _RecordingApplier:
    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, Action]] = []

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self.calls.append((message, action))


class _RecordingDraftCreator:
    def create_draft(self, in_reply_to: NormalizedMessage, body: str) -> None:
        pass


class _FakeAlerter:
    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        pass


def _row(db_path: Path, jmap_id: str) -> tuple[object, ...]:
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT tier_reached, action_taken, verdict_json FROM processed_messages WHERE jmap_id = ?",
        (jmap_id,),
    ).fetchone()
    conn.close()
    assert row is not None
    return row


def test_tier2_run_overwrites_tier1s_escalation_row(tmp_path: Path, make_message) -> None:
    """A message Tier 1 escalates (tier_reached="tier1",
    action_taken="escalate") and then runs through Tier 2 ends up with
    tier_reached="tier2" and the real action — not stuck at Tier 1's
    placeholder, and never briefly "unprocessed" in between."""
    db_path = tmp_path / "state.sqlite3"
    message = make_message(message_id="msg-1", subject="Test subject")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                "Test subject": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.95,
                    "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
                    "summary": "s",
                    "reasoning": "r",
                }
            }
        )
    )

    with StateDB(db_path) as db:
        # Tier 1: no rules match, default policy escalates.
        tier1_verdict = process_message(
            message,
            [],
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(_RecordingApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "2026-08-12T09:00:00Z",
        )
        assert tier1_verdict is not None
        assert tier1_verdict.action.type == "escalate"
        assert db.has_processed("msg-1") is False

        # Tier 2: processes the same escalated message.
        applier = _RecordingApplier()
        tier2_verdict = process_tier2_message(
            message,
            to_addresses=("me@example.com",),
            thread_prior_subject=None,
            thread_user_has_replied=False,
            available_mailboxes=("Inbox", "Needs-Reply"),
            llm_client=RecordedLLMClient(responses_path),
            executor=ActionExecutor(applier),
            draft_creator=_RecordingDraftCreator(),
            state_db=db,
            allowed_categories=["needs_reply"],
            daily_call_budget=200,
            alert_threshold=0.55,
            autoact_threshold=0.85,
            context_provider=NullContextProvider(),
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "2026-08-12T09:05:00Z",
        )

        # Tier 1 leaves the message pending; Tier 2 owns the terminal
        # processed mark and replaces the escalation placeholder.
        assert db.has_processed("msg-1") is True
        tier_reached, action_taken, verdict_json = _row(db_path, "msg-1")
        assert tier_reached == "tier2"
        assert action_taken == "tag"
        assert verdict_json is not None
        assert json.loads(verdict_json)["category"] == "needs_reply"

        # Both tiers' audit entries survive — an append-only trail,
        # not one overwriting the other's history.
        events = [e.event for e in db.get_audit_entries(jmap_id="msg-1")]
        assert events == ["escalated_pending_tier2", "tier2_action_applied"]

    assert tier2_verdict is not None
    assert applier.calls == [(message, Action(type="tag", mailbox="Needs-Reply"))]
