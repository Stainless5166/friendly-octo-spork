"""Acceptance tests for spork.core.receipts.pipeline.ArchiveReceiptAugment
(docs/DESIGN.md §9.5, M10).

Each test constructs a bare Payload[MessageMeta] and asserts what
.augment() returns/does — no full Pipeline, no process_message() call
needed, same convention every other concrete pipeline module in
spork.core.pipeline.modules already follows (§9.4).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from spork.core.models import Attachment, NormalizedMessage
from spork.core.pipeline.core import Payload
from spork.core.pipeline.meta import MessageMeta
from spork.core.receipts.archive import ReceiptArchiveError
from spork.core.receipts.llm import (
    ReceiptExtractionRequest,
    ReceiptExtractionResult,
    ReceiptExtractionUsage,
)
from spork.core.receipts.pipeline import ArchiveReceiptAugment, ReceiptArchiveComponents
from spork.core.receipts.registry import normalize_sender_domain
from spork.core.rules.schema import Action
from spork.core.state.db import StateDB


class _FakeAttachmentFetcher:
    def __init__(self, attachments: list[Attachment] | None = None) -> None:
        self.calls: list[NormalizedMessage] = []
        self._attachments = attachments or []

    def fetch_attachments(self, message: NormalizedMessage) -> list[Attachment]:
        self.calls.append(message)
        return self._attachments


class _FakeKeywordApplier:
    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, list[str]]] = []

    def apply_keywords(self, message: NormalizedMessage, keywords: list[str]) -> None:
        self.calls.append((message, list(keywords)))


class _FakeExtractionClient:
    def __init__(self, company: str, date: str) -> None:
        self.calls: list[ReceiptExtractionRequest] = []
        self._company = company
        self._date = date

    def extract_receipt(self, request: ReceiptExtractionRequest) -> ReceiptExtractionResult:
        self.calls.append(request)
        from spork.core.receipts.extract import ReceiptExtraction

        return ReceiptExtractionResult(
            extraction=ReceiptExtraction(company=self._company, date=self._date),
            usage=ReceiptExtractionUsage(tokens_in=10, tokens_out=5),
        )


def _message(**overrides: object) -> NormalizedMessage:
    defaults: dict[str, object] = {
        "message_id": "msg-1",
        "thread_id": "thread-1",
        "from_address": "billing@acmecloud.com",
        "from_domain": "acmecloud.com",
        "subject": "Your Acme Cloud receipt",
        "body_text": "Thanks for your payment.",
        "headers": {"Date": "Sat, 01 Aug 2026 00:00:00 +0000"},
    }
    defaults.update(overrides)
    return NormalizedMessage(**defaults)  # type: ignore[arg-type]


def _payload(message: NormalizedMessage) -> Payload[MessageMeta]:
    return Payload(
        text="",
        meta=MessageMeta(
            message=message,
            rules=[],
            default_unmatched_action=Action(type="escalate"),
            ts="2026-08-16T00:00:00Z",
        ),
    )


def test_known_sender_is_archived_deterministically_with_no_tier2_call(tmp_path: Path) -> None:
    output_dir = tmp_path / "receipts"
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.learn_known_sender(
            "acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
        )
        keyword_applier = _FakeKeywordApplier()
        extraction_client = _FakeExtractionClient("Should Not Be Used", "2099-01-01")
        augment = ArchiveReceiptAugment(
            db,
            ReceiptArchiveComponents(
                attachment_fetcher=_FakeAttachmentFetcher(),
                keyword_applier=keyword_applier,
                extraction_client=extraction_client,
                output_dir=output_dir,
            ),
        )

        result = augment.augment(_payload(_message()))

    assert extraction_client.calls == []  # no Tier 2 call at all
    assert keyword_applier.calls[0][1] == [
        "receipt",
        "company:Acme Cloud",
        "date:Sat, 01 Aug 2026 00:00:00 +0000",
    ]
    assert result.meta.audit_event == "receipt_archived"
    assert result.meta.audit_detail_json is not None
    assert "Acme Cloud" in result.meta.audit_detail_json


def test_unrecognized_sender_calls_tier2_once_and_learns_the_sender(tmp_path: Path) -> None:
    output_dir = tmp_path / "receipts"
    with StateDB(tmp_path / "state.sqlite3") as db:
        extraction_client = _FakeExtractionClient("New Vendor Inc", "2026-08-01")
        augment = ArchiveReceiptAugment(
            db,
            ReceiptArchiveComponents(
                attachment_fetcher=_FakeAttachmentFetcher(),
                keyword_applier=_FakeKeywordApplier(),
                extraction_client=extraction_client,
                output_dir=output_dir,
            ),
        )

        augment.augment(
            _payload(_message(from_address="billing@newvendor.io", from_domain="newvendor.io"))
        )

        assert len(extraction_client.calls) == 1
        assert extraction_client.calls[0].from_domain == "newvendor.io"
        learned = db.get_known_sender(normalize_sender_domain("newvendor.io"))
        assert learned is not None
        assert learned.company == "New Vendor Inc"
        assert learned.learned_from == "tier2"


def test_a_message_with_attachments_produces_a_multi_page_saved_pdf(tmp_path: Path) -> None:
    output_dir = tmp_path / "receipts"
    attachment = Attachment(filename="statement.csv", content_type="text/csv", data=b"x,y\n1,2\n")
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.learn_known_sender(
            "acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
        )
        fetcher = _FakeAttachmentFetcher([attachment])
        augment = ArchiveReceiptAugment(
            db,
            ReceiptArchiveComponents(
                attachment_fetcher=fetcher,
                keyword_applier=_FakeKeywordApplier(),
                extraction_client=_FakeExtractionClient("unused", "unused"),
                output_dir=output_dir,
            ),
        )

        augment.augment(_payload(_message()))

    assert len(fetcher.calls) == 1
    saved = list(output_dir.glob("*.pdf"))
    assert len(saved) == 1
    reader = PdfReader(saved[0])
    assert len(reader.pages) == 2  # cover + the one attachment page


def test_a_write_failure_propagates_instead_of_being_swallowed(tmp_path: Path) -> None:
    """An unwritable output location must not silently succeed -- the
    caller (WriteAuditEntryFilter/MarkProcessedFilter) never runs,
    leaving the message retryable, same fail-open-for-retry contract
    m2_rules.feature's @audit scenario already specifies."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    with StateDB(tmp_path / "state.sqlite3") as db:
        db.learn_known_sender(
            "acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
        )
        augment = ArchiveReceiptAugment(
            db,
            ReceiptArchiveComponents(
                attachment_fetcher=_FakeAttachmentFetcher(),
                keyword_applier=_FakeKeywordApplier(),
                extraction_client=_FakeExtractionClient("unused", "unused"),
                output_dir=blocker / "sub",
            ),
        )

        with pytest.raises(ReceiptArchiveError):
            augment.augment(_payload(_message()))
