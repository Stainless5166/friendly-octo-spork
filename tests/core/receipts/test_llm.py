"""Acceptance tests for spork.core.receipts.llm (docs/DESIGN.md §9.5, §10.5).

RecordedReceiptExtractionClient is the ReceiptExtractionClient
equivalent of RecordedLLMClient (§10.5) -- a second, fully real
adapter with no NotImplementedError anywhere, keyed by from_domain
(not subject) since a receipt extraction fixture entry is meant to
describe "how spork resolves this sender," not one specific email.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spork.core.receipts.extract import ReceiptExtraction
from spork.core.receipts.llm import (
    ReceiptExtractionRequest,
    RecordedReceiptExtractionClient,
    RecordedReceiptExtractionsLoadError,
    UnrecordedReceiptExtractionError,
)


def _request(from_domain: str = "newvendor.io") -> ReceiptExtractionRequest:
    return ReceiptExtractionRequest(
        subject="Your receipt",
        from_address=f"billing@{from_domain}",
        from_domain=from_domain,
        body_text="Thanks for your payment of $12.00 on 2026-08-01.",
    )


def _write_responses(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "newvendor.io": {"company": "New Vendor Inc", "date": "2026-08-01"},
                "otherco.example": {"company": "Other Co", "date": "2026-08-02"},
            }
        )
    )


def test_extract_receipt_returns_the_recorded_extraction_for_a_matching_domain(
    tmp_path: Path,
) -> None:
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path)
    client = RecordedReceiptExtractionClient(responses_path)

    result = client.extract_receipt(_request("newvendor.io"))

    assert result.extraction == ReceiptExtraction(company="New Vendor Inc", date="2026-08-01")
    assert result.usage.tokens_in == 0
    assert result.usage.tokens_out == 0


def test_extract_receipt_picks_the_matching_domain_not_just_the_first(tmp_path: Path) -> None:
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path)
    client = RecordedReceiptExtractionClient(responses_path)

    result = client.extract_receipt(_request("otherco.example"))

    assert result.extraction.company == "Other Co"


def test_extract_receipt_raises_for_an_unrecorded_domain(tmp_path: Path) -> None:
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path)
    client = RecordedReceiptExtractionClient(responses_path)

    with pytest.raises(UnrecordedReceiptExtractionError):
        client.extract_receipt(_request("unrecorded.example"))


def test_missing_responses_file_raises_load_error(tmp_path: Path) -> None:
    with pytest.raises(RecordedReceiptExtractionsLoadError):
        RecordedReceiptExtractionClient(tmp_path / "does-not-exist.json")


def test_malformed_json_raises_load_error(tmp_path: Path) -> None:
    path = tmp_path / "responses.json"
    path.write_text("{not valid json")

    with pytest.raises(RecordedReceiptExtractionsLoadError):
        RecordedReceiptExtractionClient(path)


def test_non_object_top_level_raises_load_error(tmp_path: Path) -> None:
    path = tmp_path / "responses.json"
    path.write_text(json.dumps(["not", "an", "object"]))

    with pytest.raises(RecordedReceiptExtractionsLoadError):
        RecordedReceiptExtractionClient(path)


def test_entry_missing_a_required_field_raises_load_error(tmp_path: Path) -> None:
    path = tmp_path / "responses.json"
    path.write_text(json.dumps({"newvendor.io": {"company": "New Vendor Inc"}}))  # no date

    with pytest.raises(RecordedReceiptExtractionsLoadError):
        RecordedReceiptExtractionClient(path)
