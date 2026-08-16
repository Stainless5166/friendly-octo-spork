"""Acceptance tests for process_message() (docs/DESIGN.md §9).

Ties the rule engine, ActionExecutor, and StateDB together — exercised
here against the real rule engine and a real (tmp_path) StateDB, with
a stub ActionApplier standing in for any real backend, and an injected
clock for deterministic timestamps.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.models import NormalizedMessage
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.rules.schema import Action, Condition, Rule
from spork.core.state.db import StateDB


class _RecordingApplier:
    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, Action]] = []

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self.calls.append((message, action))


class _FakeAlerter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        self.calls.append({"title": title, "body": body, "url": url, "urgency": urgency})


def test_process_message_skips_already_processed_messages(tmp_path: Path, make_message) -> None:
    """A message already marked processed is never re-evaluated or
    re-acted on — the idempotency guarantee (docs/DESIGN.md §11)."""
    applier = _RecordingApplier()
    with StateDB(tmp_path / "state.sqlite3") as db:
        message = make_message(message_id="msg-1")
        db.mark_processed(message.message_id, thread_id=message.thread_id, processed_at="t0")

        verdict = process_message(
            message,
            [],
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
        )

    assert verdict is None
    assert applier.calls == []


def test_process_message_with_force_reprocesses_an_already_processed_message(
    tmp_path: Path, make_message
) -> None:
    """force=True (docs/DESIGN.md §9.4, for spork reclassify) bypasses
    IdempotencyGateSelector entirely — an already-processed message is
    evaluated and acted on again, and its processed_messages row is
    overwritten (MarkProcessedFilter's existing upsert), not left as
    a duplicate or an error."""
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1", from_domain="newsletter.example.com")
    rules = [
        Rule(
            id="file-newsletter",
            when=Condition(from_domain_in=["newsletter.example.com"]),
            action=Action(type="move", mailbox="Reading"),
        )
    ]
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.mark_processed(message.message_id, thread_id=message.thread_id, processed_at="t0")

        verdict = process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
            force=True,
        )

    assert verdict is not None
    assert verdict.action.type == "move"
    assert applier.calls == [(message, Action(type="move", mailbox="Reading"))]


def test_process_message_applies_matched_rule_action_and_marks_processed(
    tmp_path: Path, make_message
) -> None:
    """A message matching a terminal rule gets that action applied and
    is recorded as processed."""
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1", from_domain="newsletter.example.com")
    rules = [
        Rule(
            id="file-newsletter",
            when=Condition(from_domain_in=["newsletter.example.com"]),
            action=Action(type="move", mailbox="Reading"),
        )
    ]

    with StateDB(tmp_path / "state.sqlite3") as db:
        verdict = process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
        )

        assert db.has_processed("msg-1") is True

    assert verdict is not None
    assert verdict.matched_rule_id == "file-newsletter"
    assert applier.calls == [(message, Action(type="move", mailbox="Reading"))]


def test_process_message_traces_every_stage_it_runs(
    tmp_path: Path, make_message, caplog: pytest.LogCaptureFixture
) -> None:
    """docs/DESIGN.md §9.4/§12.2 (M7): every module build_default_pipeline()
    composes is wrapped with TracingStage/TracingSelector — a real
    message's full journey through one pipeline run is reconstructable
    from logs alone, not just the alert-worthy stages."""
    caplog.set_level(logging.INFO)
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1", from_domain="newsletter.example.com")
    rules = [
        Rule(
            id="file-newsletter",
            when=Condition(from_domain_in=["newsletter.example.com"]),
            action=Action(type="move", mailbox="Reading"),
        )
    ]

    with StateDB(tmp_path / "state.sqlite3") as db:
        process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
        )

    for stage_name in (
        "IdempotencyGateSelector",
        "TimestampFilter",
        "CorrelationIdFilter",
        "RuleEvaluationSelector",
        "ApplyActionFilter",
        "WriteAuditEntryFilter",
        "MarkProcessedFilter",
    ):
        assert stage_name in caplog.text, f"{stage_name} never traced"


def test_process_message_writes_an_audit_entry_for_applied_actions(
    tmp_path: Path, make_message
) -> None:
    """Applying an action leaves a trace in the audit log."""
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1")
    rules = [Rule(id="always-ignore", when=Condition(always=True), action=Action(type="ignore"))]

    with StateDB(tmp_path / "state.sqlite3") as db:
        process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
        )

        entries = db.get_audit_entries(jmap_id="msg-1")

    assert len(entries) == 1
    assert entries[0].ts == "t1"


def test_process_message_handles_escalate_without_calling_executor(
    tmp_path: Path, make_message
) -> None:
    """An escalate verdict is recorded pending Tier 2 and never reaches
    the executor, which would reject it anyway."""
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1")

    with StateDB(tmp_path / "state.sqlite3") as db:
        verdict = process_message(
            message,
            [],
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
        )

        assert db.has_processed("msg-1") is False

    assert verdict is not None
    assert verdict.action.type == "escalate"
    assert applier.calls == []


def test_escalation_remains_retryable_until_tier2_completes(tmp_path: Path, make_message) -> None:
    """Tier 1 must not permanently consume work owned by Tier 2."""
    message = make_message(message_id="msg-pending")
    with StateDB(tmp_path / "state.sqlite3") as db:
        first = process_message(
            message,
            [],
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(_RecordingApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
        )
        second = process_message(
            message,
            [],
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(_RecordingApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t2",
        )

        assert db.has_processed(message.message_id) is False

    assert first is not None and first.action.type == "escalate"
    assert second is not None and second.action.type == "escalate"


def test_process_message_alerts_immediately_for_a_vip_sender_rule(
    tmp_path: Path, make_message
) -> None:
    """End to end: a VIP-sender rule (alert_immediately=True) escalates
    and fires a real alert through the injected PipelineObserver,
    without needing Tier 2 to run at all (docs/DESIGN.md §12.2)."""
    applier = _RecordingApplier()
    alerter = _FakeAlerter()
    message = make_message(message_id="msg-1", from_address="boss@example.com")
    rules = [
        Rule(
            id="vip-senders",
            when=Condition(from_in=["boss@example.com"]),
            action=Action(type="escalate", reason="vip_sender", alert_immediately=True),
        )
    ]

    with StateDB(tmp_path / "state.sqlite3") as db:
        process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(alerter),
            now=lambda: "t1",
        )

    assert len(alerter.calls) == 1
    assert "vip_sender" in str(alerter.calls[0]["title"])


def test_process_message_returns_the_verdict(tmp_path: Path, make_message) -> None:
    """The verdict that was actually acted on is returned, so a caller
    (e.g. the daemon's main loop, for logging) doesn't need to
    re-derive it."""
    applier = _RecordingApplier()
    message = make_message(message_id="msg-1")
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="ignore"))]

    with StateDB(tmp_path / "state.sqlite3") as db:
        verdict = process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
        )

    assert verdict is not None
    assert verdict.matched_rule_id == "r1"
    assert verdict.action == Action(type="ignore")


def test_process_message_archives_a_matched_receipt_end_to_end(
    tmp_path: Path, make_message
) -> None:
    """A message matching an archive_receipt rule, with receipt_archive
    components wired, is archived and marked processed via the full
    process_message() call -- not just the standalone Augment
    (docs/DESIGN.md §9.5, M10)."""
    from spork.core.receipts.llm import (
        ReceiptExtractionRequest,
        ReceiptExtractionResult,
        ReceiptExtractionUsage,
    )
    from spork.core.receipts.pipeline import ReceiptArchiveComponents

    class _FakeAttachmentFetcher:
        def fetch_attachments(self, message):  # type: ignore[no-untyped-def]
            return []

    class _FakeKeywordApplier:
        def __init__(self) -> None:
            self.calls: list[tuple[object, list[str]]] = []

        def apply_keywords(self, message, keywords):  # type: ignore[no-untyped-def]
            self.calls.append((message, list(keywords)))

    class _FakeExtractionClient:
        def extract_receipt(self, request: ReceiptExtractionRequest) -> ReceiptExtractionResult:
            from spork.core.receipts.extract import ReceiptExtraction

            return ReceiptExtractionResult(
                extraction=ReceiptExtraction(company="Acme Cloud", date="2026-08-01"),
                usage=ReceiptExtractionUsage(tokens_in=0, tokens_out=0),
            )

    message = make_message(message_id="msg-1", from_domain="acmecloud.com")
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="archive_receipt"))]
    keyword_applier = _FakeKeywordApplier()

    with StateDB(tmp_path / "state.sqlite3") as db:
        verdict = process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(_RecordingApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
            receipt_archive=ReceiptArchiveComponents(
                attachment_fetcher=_FakeAttachmentFetcher(),
                keyword_applier=keyword_applier,
                extraction_client=_FakeExtractionClient(),
                output_dir=tmp_path / "receipts",
            ),
        )

        assert db.has_processed("msg-1") is True

    assert verdict is not None
    assert verdict.action.type == "archive_receipt"
    assert keyword_applier.calls[0][1] == ["receipt", "company:Acme Cloud", "date:2026-08-01"]
    assert len(list((tmp_path / "receipts").glob("*.pdf"))) == 1


def test_process_message_without_receipt_archive_configured_fails_clearly(
    tmp_path: Path, make_message
) -> None:
    """An archive_receipt rule with no receipt_archive= given is a
    config error, not a silent no-op -- same "fail loud" stance as
    everything else in this pipeline (docs/DESIGN.md §9.5, M10)."""
    from spork.core.pipeline.core import UnknownBranchError

    message = make_message(message_id="msg-1")
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="archive_receipt"))]

    with (
        StateDB(tmp_path / "state.sqlite3") as db,
        pytest.raises(UnknownBranchError),
    ):
        process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(_RecordingApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
        )
