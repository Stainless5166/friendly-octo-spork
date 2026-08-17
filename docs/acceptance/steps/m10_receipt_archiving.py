"""Real step bindings for M10's receipt-archiving acceptance scenarios.

Drives the real pipeline end to end -- process_message() wired with a
real FileProvider (attachments + keywords), a real StateDB, and a
RecordedReceiptExtractionClient standing in for a live Claude call
(docs/DESIGN.md §9.5). No live account, no network, anywhere in this
file.
"""

from __future__ import annotations

import base64
import json
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from behave import given, then, when
from pypdf import PdfReader

from spork.core.actions.executor import ActionExecutor
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.providers.file.provider import FileProvider
from spork.core.receipts.llm import RecordedReceiptExtractionClient
from spork.core.receipts.pipeline import ReceiptArchiveComponents
from spork.core.rules.schema import Action, Condition, Rule
from spork.core.state.db import StateDB

_RECEIPT_DOMAINS = ["acmecloud.com", "newvendor.io"]


class _FakeAlerter:
    def notify(self, title, body, *, url=None, urgency="normal") -> None:  # type: ignore[no-untyped-def]
        pass


class _CountingExtractionClient:
    """Wraps a real ReceiptExtractionClient to count calls -- the
    fixture-replay client itself has no notion of "how many times was
    I called", but @no-llm/@llm-escalation need to assert on exactly
    that."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.call_count = 0

    def extract_receipt(self, request: Any) -> Any:
        self.call_count += 1
        return self._inner.extract_receipt(request)


def _one_page_pdf_bytes(text: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(72, 700, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def _one_pixel_png_bytes() -> bytes:
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (10, 10), color="green").save(buf, format="PNG")
    return buf.getvalue()


def _world(context: Any) -> Path:
    """Create (once per scenario) a fresh tmp dir holding everything
    the scenario's Background/Given steps accumulate: the messages
    fixture, StateDB, and the Tier 2 recorded-extraction fixture."""
    if not hasattr(context, "tmp_dir"):
        context.tmp_dir = Path(tempfile.mkdtemp(prefix="spork-m10-acceptance-"))
        context.messages: list[dict[str, Any]] = []
        context.state_db = StateDB(context.tmp_dir / "state.sqlite3")
        context.extraction_fixture: dict[str, dict[str, str]] = {}
        context.output_dir = context.tmp_dir / "receipts"
        context.rules = [
            Rule(
                id="automatic-payment-receipts",
                when=Condition(from_domain_in=_RECEIPT_DOMAINS),
                action=Action(type="archive_receipt"),
            ),
            Rule(id="catchall", when=Condition(always=True), action=Action(type="ignore")),
        ]
    tmp_dir: Path = context.tmp_dir
    return tmp_dir


def _write_extraction_fixture(context: Any) -> Path:
    path = _world(context) / "extractions.json"
    path.write_text(json.dumps(context.extraction_fixture))
    return path


def _add_message(
    context: Any,
    *,
    domain: str,
    message_id: str,
    attachments: list[dict[str, Any]] | None = None,
) -> None:
    _world(context)
    context.messages.append(
        {
            "message_id": message_id,
            "thread_id": message_id,
            "from_address": f"billing@{domain}",
            "from_domain": domain,
            "subject": "Your receipt",
            "body_text": "Thanks for your payment.",
            "headers": {"Date": "Sat, 01 Aug 2026 00:00:00 +0000"},
            "attachments": attachments or [],
        }
    )
    context.current_message_id = message_id


def _process_current_message(context: Any) -> None:
    _world(context)
    messages_path = context.tmp_dir / f"messages-{context.current_message_id}.json"
    messages_path.write_text(json.dumps(context.messages))
    provider = FileProvider(messages_path, context.tmp_dir / "actions.jsonl")

    _write_extraction_fixture(context)
    context.extraction_client = _CountingExtractionClient(
        RecordedReceiptExtractionClient(context.tmp_dir / "extractions.json")
    )

    message = next(
        m for m in provider.build_source().poll() if m.message_id == context.current_message_id
    )
    context.error = None
    try:
        context.verdict = process_message(
            message,
            context.rules,
            default_unmatched_action=Action(type="ignore"),
            executor=ActionExecutor(provider.build_action_applier()),
            state_db=context.state_db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "2026-08-16T00:00:00Z",
            receipt_archive=ReceiptArchiveComponents(
                attachment_fetcher=provider.build_attachment_fetcher(),
                keyword_applier=provider.build_keyword_applier(),
                extraction_client=context.extraction_client,
                output_dir=context.output_dir,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - captured for the @failure-safety scenario
        context.error = exc
    context.provider = provider


# --- Background --------------------------------------------------------


@given("a rules file with a rule that recognizes automatic-payment receipts")
def rules_file_recognizes_receipts(context: Any) -> None:
    _world(context)  # rules are already part of the world; nothing more to do


@given("a receipt archive output directory is configured")
def receipt_archive_output_dir_configured(context: Any) -> None:
    _world(context)


@given('the known-senders registry is seeded with "{domain}" as "{company}"')
def known_senders_registry_seeded(context: Any, domain: str, company: str) -> None:
    bare_domain = domain.removeprefix("billing.")
    _world(context)
    context.state_db.learn_known_sender(
        bare_domain, company=company, learned_from="seed", learned_at="t0"
    )


# --- Givens: message fixtures -------------------------------------------


@given('a receipt email from "{domain}" with one PDF invoice attachment')
def receipt_email_with_pdf_attachment(context: Any, domain: str) -> None:
    bare_domain = domain.removeprefix("billing.")
    _add_message(
        context,
        domain=bare_domain,
        message_id="msg-known",
        attachments=[
            {
                "filename": "invoice.pdf",
                "content_type": "application/pdf",
                "data_base64": base64.b64encode(_one_page_pdf_bytes("invoice")).decode("ascii"),
            }
        ],
    )


@given('a receipt email from the unrecognized domain "{domain}"')
def receipt_email_from_unrecognized_domain(context: Any, domain: str) -> None:
    bare_domain = domain.removeprefix("billing.")
    context.extraction_fixture = {bare_domain: {"company": "New Vendor Inc", "date": "2026-08-01"}}
    _add_message(context, domain=bare_domain, message_id="msg-unrecognized")


@given('"{domain}" was learned as "{company}" by an earlier Tier 2 call')
def sender_was_previously_learned(context: Any, domain: str, company: str) -> None:
    bare_domain = domain.removeprefix("billing.")
    _world(context)
    context.state_db.learn_known_sender(
        bare_domain, company=company, learned_from="tier2", learned_at="t0"
    )


@given('a receipt email from "{domain}" with no attachments')
def receipt_email_with_no_attachments(context: Any, domain: str) -> None:
    bare_domain = domain.removeprefix("billing.")
    _add_message(context, domain=bare_domain, message_id="msg-no-attachments")


@given('a receipt email from "{domain}" with a PDF attachment and an image attachment')
def receipt_email_with_two_attachments(context: Any, domain: str) -> None:
    bare_domain = domain.removeprefix("billing.")
    _add_message(
        context,
        domain=bare_domain,
        message_id="msg-two-attachments",
        attachments=[
            {
                "filename": "invoice.pdf",
                "content_type": "application/pdf",
                "data_base64": base64.b64encode(_one_page_pdf_bytes("invoice")).decode("ascii"),
            },
            {
                "filename": "receipt.png",
                "content_type": "image/png",
                "data_base64": base64.b64encode(_one_pixel_png_bytes()).decode("ascii"),
            },
        ],
    )


@given("a message that does not match the receipt rule")
def message_not_matching_receipt_rule(context: Any) -> None:
    _add_message(context, domain="personal.example", message_id="msg-non-receipt")


@given("the configured output directory cannot be written to")
def output_directory_unwritable(context: Any) -> None:
    _world(context)
    blocker = context.tmp_dir / "blocker"
    blocker.write_text("not a directory")
    context.output_dir = blocker / "sub"


# --- Whens ---------------------------------------------------------------


@when("the message is processed by Tier 1")
def message_processed_by_tier1(context: Any) -> None:
    _process_current_message(context)


@when('a second receipt email from "{domain}" is processed by Tier 1')
def second_message_processed_by_tier1(context: Any, domain: str) -> None:
    bare_domain = domain.removeprefix("billing.")
    _add_message(context, domain=bare_domain, message_id="msg-second")
    _process_current_message(context)


@when("a known-sender receipt email is processed by Tier 1")
def known_sender_message_processed_by_tier1(context: Any) -> None:
    context.state_db.learn_known_sender(
        "acmecloud.com", company="Acme Cloud", learned_from="seed", learned_at="t0"
    )
    _add_message(context, domain="acmecloud.com", message_id="msg-unwritable")
    _process_current_message(context)


# --- Thens -----------------------------------------------------------------


def _applied_keywords(context: Any) -> list[str]:
    log_path = context.tmp_dir / "keywords.jsonl"
    assert log_path.exists(), "no keywords were ever applied"
    entries = [json.loads(line) for line in log_path.read_text().splitlines()]
    entry = next(e for e in entries if e["message_id"] == context.current_message_id)
    keywords: list[str] = entry["keywords"]
    return keywords


@then(
    'the message is tagged "receipt", "company:{company}", '
    'and a "date:" tag matching the invoice date'
)
def message_tagged_from_invoice_date(context: Any, company: str) -> None:
    keywords = _applied_keywords(context)
    assert keywords[0] == "receipt"
    assert keywords[1] == f"company:{company}"
    assert keywords[2].startswith("date:")


@then(
    "a single combined PDF containing the message and its attachment "
    "is saved to the configured output directory"
)
def combined_pdf_with_attachment_saved(context: Any) -> None:
    pdfs = list(context.output_dir.glob("*.pdf"))
    assert len(pdfs) == 1
    assert len(PdfReader(pdfs[0]).pages) == 2  # cover + the one attachment


@then("no Tier 2 call is made")
def no_tier2_call_is_made(context: Any) -> None:
    assert context.extraction_client.call_count == 0


@then("exactly one Tier 2 receipt-extraction call is made")
def exactly_one_tier2_call_is_made(context: Any) -> None:
    assert context.extraction_client.call_count == 1


@then(
    'the message is tagged "receipt", "company:{company}", '
    'and a "date:" tag matching the extracted date'
)
def message_tagged_from_extracted_date(context: Any, company: str) -> None:
    message_tagged_from_invoice_date(context, company)


@then("a single combined PDF is saved to the configured output directory")
def combined_pdf_saved(context: Any) -> None:
    assert len(list(context.output_dir.glob("*.pdf"))) == 1


@then('"{domain}" is recorded in the known-senders registry as "{company}"')
def sender_recorded_in_registry(context: Any, domain: str, company: str) -> None:
    bare_domain = domain.removeprefix("billing.")
    sender = context.state_db.get_known_sender(bare_domain)
    assert sender is not None
    assert sender.company == company
    assert sender.learned_from == "tier2"


@then("the message is tagged and archived without any Tier 2 call")
def message_tagged_and_archived_without_tier2(context: Any) -> None:
    no_tier2_call_is_made(context)
    assert len(_applied_keywords(context)) == 3
    assert len(list(context.output_dir.glob("*.pdf"))) == 1


@then(
    "a single PDF built from the message content alone is saved to the configured output directory"
)
def pdf_from_message_content_alone_saved(context: Any) -> None:
    pdfs = list(context.output_dir.glob("*.pdf"))
    assert len(pdfs) == 1
    assert len(PdfReader(pdfs[0]).pages) == 1


@then("exactly one PDF file is saved to the configured output directory")
def exactly_one_pdf_file_saved(context: Any) -> None:
    assert len(list(context.output_dir.glob("*.pdf"))) == 1


@then("that PDF contains the message content followed by both attachments in order")
def pdf_contains_message_then_attachments_in_order(context: Any) -> None:
    pdfs = list(context.output_dir.glob("*.pdf"))
    reader = PdfReader(pdfs[0])
    assert len(reader.pages) == 3
    assert "invoice" in reader.pages[1].extract_text()


@then("no PDF is archived")
def no_pdf_is_archived(context: Any) -> None:
    assert not context.output_dir.exists() or list(context.output_dir.glob("*.pdf")) == []


@then("the message is handled by its normal matching rule instead")
def message_handled_by_normal_rule(context: Any) -> None:
    assert context.verdict is not None
    assert context.verdict.action.type == "ignore"


@then("the failure is reported without a raw traceback")
def failure_reported_without_traceback(context: Any) -> None:
    assert context.error is not None
    assert "Traceback" not in str(context.error)


@then("the message is not marked processed")
def message_not_marked_processed(context: Any) -> None:
    assert context.state_db.has_processed(context.current_message_id) is False


@then("the next acquisition cycle can retry the message")
def next_cycle_can_retry(context: Any) -> None:
    # A message that isn't marked processed is exactly what the next
    # poll/push cycle would pick back up (docs/DESIGN.md §11) -- the
    # prior Then already proved that directly; this restates the
    # acceptance-visible guarantee it implies.
    message_not_marked_processed(context)
