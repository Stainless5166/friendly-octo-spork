"""Real step bindings for the recorded Tier 2 receipt-extraction module
(spork.core.receipts.llm.RecordedReceiptExtractionClient).

Fully implemented, unlike m10_receipt_archiving.feature (still @wip).
No live model call anywhere -- a fixture file built per scenario in a
fresh tmp directory.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from behave import given, then, when

from spork.core.receipts.llm import (
    ReceiptExtractionRequest,
    RecordedReceiptExtractionClient,
    UnrecordedReceiptExtractionError,
)


def _fixture_path(context: Any) -> Path:
    if not hasattr(context, "fixture_path"):
        context.fixture_path = (
            Path(tempfile.mkdtemp(prefix="spork-m10c-acceptance-")) / "extractions.json"
        )
        context.fixture_path.write_text("{}")
    path: Path = context.fixture_path
    return path


def _fixture_data(context: Any) -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = json.loads(_fixture_path(context).read_text())
    return data


@given('a recorded extraction of "{company}" / "{date}" for domain "{domain}"')
def recorded_extraction_for_domain(context: Any, company: str, date: str, domain: str) -> None:
    data = _fixture_data(context)
    data[domain] = {"company": company, "date": date}
    _fixture_path(context).write_text(json.dumps(data))


@when('a receipt from "{domain}" is extracted via the recorded client')
def receipt_extracted_via_recorded_client(context: Any, domain: str) -> None:
    client = RecordedReceiptExtractionClient(_fixture_path(context))
    request = ReceiptExtractionRequest(
        subject="Your receipt",
        from_address=f"billing@{domain}",
        from_domain=domain,
        body_text="Thanks for your payment.",
    )
    context.error = None
    try:
        context.result = client.extract_receipt(request)
    except UnrecordedReceiptExtractionError as exc:
        context.result = None
        context.error = exc


@then('the recorded extraction is company "{company}" dated "{date}"')
def extraction_succeeds_with_company_and_date(context: Any, company: str, date: str) -> None:
    assert context.error is None, f"unexpected error: {context.error}"
    assert context.result is not None
    assert context.result.extraction.company == company
    assert context.result.extraction.date == date


@then("the recorded client reports no extraction is available for that domain")
def recorded_client_reports_no_extraction(context: Any) -> None:
    assert isinstance(context.error, UnrecordedReceiptExtractionError)
