"""Real step bindings for the receipt PDF building/archiving module.

Unlike m10_receipt_archiving.feature (still @wip -- the full pipeline
isn't wired up yet), this feature exercises a real, already-implemented
module (spork.core.receipts.pdf/archive) directly, no fixtures beyond
what these steps construct in-memory.
"""

from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from behave import given, then, when
from pypdf import PdfReader

from spork.core.models import Attachment, NormalizedMessage
from spork.core.receipts.archive import save_pdf
from spork.core.receipts.pdf import build_receipt_pdf


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
    Image.new("RGB", (10, 10), color="blue").save(buf, format="PNG")
    return buf.getvalue()


@given("a receipt message with no attachments")
def message_with_no_attachments(context: Any) -> None:
    context.message = NormalizedMessage(
        message_id="msg-acme-1",
        thread_id="thread-1",
        from_address="billing@acmecloud.com",
        from_domain="acmecloud.com",
        subject="Your Acme Cloud receipt",
        body_text="Thanks for your payment of $12.00.",
    )
    context.company = "Acme Cloud"
    context.date = "2026-08-01"
    context.attachments = []


@given("a receipt message with a one-page PDF attachment and an image attachment")
def message_with_pdf_and_image_attachments(context: Any) -> None:
    message_with_no_attachments(context)
    context.attachments = [
        Attachment(
            filename="invoice.pdf",
            content_type="application/pdf",
            data=_one_page_pdf_bytes("invoice page"),
        ),
        Attachment(filename="receipt.png", content_type="image/png", data=_one_pixel_png_bytes()),
    ]


@given("a receipt message with a CSV attachment")
def message_with_csv_attachment(context: Any) -> None:
    message_with_no_attachments(context)
    context.attachments = [
        Attachment(
            filename="statement.csv",
            content_type="text/csv",
            data=b"date,amount\n2026-08-01,12.00\n",
        )
    ]


@when("the message is built into a receipt PDF and archived")
def build_and_archive(context: Any) -> None:
    # A fresh directory per scenario -- avoids collisions between
    # scenarios/runs entirely, rather than clearing a fixed shared path.
    context.output_dir = Path(tempfile.mkdtemp(prefix="spork-m9a-acceptance-"))
    pdf_bytes = build_receipt_pdf(
        context.message, context.attachments, company=context.company, date=context.date
    )
    context.archived_path = save_pdf(
        pdf_bytes,
        output_dir=context.output_dir,
        message_id=context.message.message_id,
        company=context.company,
        date=context.date,
    )


@then("exactly one PDF file exists in the output directory")
def exactly_one_pdf_file_exists(context: Any) -> None:
    pdf_files = list(context.output_dir.glob("*.pdf"))
    assert len(pdf_files) == 1, pdf_files
    assert pdf_files[0] == context.archived_path


@then("the PDF has exactly one page containing the company and date")
def pdf_has_one_page_with_company_and_date(context: Any) -> None:
    reader = PdfReader(context.archived_path)
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert context.company in text
    assert context.date in text


@then("the archived PDF has 3 pages in cover, PDF-attachment, image-attachment order")
def archived_pdf_has_three_pages_in_order(context: Any) -> None:
    reader = PdfReader(context.archived_path)
    assert len(reader.pages) == 3
    assert context.company in reader.pages[0].extract_text()
    assert "invoice page" in reader.pages[1].extract_text()
    # page 2 (the image) has no extractable text of its own -- its
    # presence as a third page is the assertion.


@then("the archived PDF names the CSV attachment's filename on its own page")
def archived_pdf_names_csv_attachment(context: Any) -> None:
    reader = PdfReader(context.archived_path)
    assert len(reader.pages) == 2
    assert "statement.csv" in reader.pages[1].extract_text()


@then("the archived filename contains the date, the company, and the message id")
def archived_filename_contains_date_company_message_id(context: Any) -> None:
    name = context.archived_path.name.lower()
    assert context.date in name
    assert "acme-cloud" in name
    assert context.message.message_id.lower() in name
