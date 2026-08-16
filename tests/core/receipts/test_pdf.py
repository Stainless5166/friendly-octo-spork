"""Acceptance tests for spork.core.receipts.pdf.build_receipt_pdf() (docs/DESIGN.md §9.5).

Each test opens the returned bytes with pypdf to assert on real PDF
structure (page count, extracted text) — never just "some bytes came
back". No mocking: reportlab/pypdf are real, already-installed
dependencies (spork[receipts]).
"""

from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from spork.core.models import Attachment, NormalizedMessage
from spork.core.receipts.pdf import build_receipt_pdf


def _message(**overrides: object) -> NormalizedMessage:
    defaults: dict[str, object] = {
        "message_id": "msg-1",
        "thread_id": "thread-1",
        "from_address": "billing@acmecloud.com",
        "from_domain": "acmecloud.com",
        "subject": "Your Acme Cloud receipt",
        "body_text": "Thanks for your payment of $12.00 on 2026-08-01.",
    }
    defaults.update(overrides)
    return NormalizedMessage(**defaults)  # type: ignore[arg-type]


def _one_page_pdf_bytes(text: str = "attachment page") -> bytes:
    """Build a minimal real one-page PDF to use as a PDF attachment fixture."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(72, 700, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def _one_pixel_png_bytes() -> bytes:
    """A tiny real PNG (via Pillow) to use as an image attachment fixture."""
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    return buf.getvalue()


def test_no_attachments_produces_a_single_cover_page_with_the_tags() -> None:
    pdf_bytes = build_receipt_pdf(_message(), [], company="Acme Cloud", date="2026-08-01")
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "Acme Cloud" in text
    assert "2026-08-01" in text
    assert "receipt" in text.lower()
    assert "Your Acme Cloud receipt" in text


def test_a_pdf_attachment_is_merged_page_for_page() -> None:
    attachment_pdf = _one_page_pdf_bytes()
    attachment = Attachment(filename="invoice.pdf", content_type="application/pdf", data=attachment_pdf)
    pdf_bytes = build_receipt_pdf(
        _message(), [attachment], company="Acme Cloud", date="2026-08-01"
    )
    reader = PdfReader(BytesIO(pdf_bytes))
    # One cover page + the one page from the merged attachment.
    assert len(reader.pages) == 2
    assert "attachment page" in reader.pages[1].extract_text()


def test_an_image_attachment_becomes_its_own_page() -> None:
    attachment = Attachment(filename="receipt.png", content_type="image/png", data=_one_pixel_png_bytes())
    pdf_bytes = build_receipt_pdf(
        _message(), [attachment], company="Acme Cloud", date="2026-08-01"
    )
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) == 2


def test_an_unrenderable_attachment_gets_a_placeholder_page_naming_it() -> None:
    attachment = Attachment(
        filename="statement.csv", content_type="text/csv", data=b"date,amount\n2026-08-01,12.00\n"
    )
    pdf_bytes = build_receipt_pdf(
        _message(), [attachment], company="Acme Cloud", date="2026-08-01"
    )
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) == 2
    assert "statement.csv" in reader.pages[1].extract_text()


def test_multiple_attachments_are_combined_in_input_order() -> None:
    first = Attachment(filename="a.pdf", content_type="application/pdf", data=_one_page_pdf_bytes("first"))
    second = Attachment(
        filename="b.png", content_type="image/png", data=_one_pixel_png_bytes()
    )
    pdf_bytes = build_receipt_pdf(
        _message(), [first, second], company="Acme Cloud", date="2026-08-01"
    )
    reader = PdfReader(BytesIO(pdf_bytes))
    # cover page, then "a.pdf"'s one page, then "b.png"'s one page.
    assert len(reader.pages) == 3
    assert "first" in reader.pages[1].extract_text()


def test_result_is_exactly_one_valid_pdf_document() -> None:
    pdf_bytes = build_receipt_pdf(_message(), [], company="Acme Cloud", date="2026-08-01")
    assert pdf_bytes.startswith(b"%PDF-")
    # Raises if pypdf can't parse it as one coherent document.
    PdfReader(BytesIO(pdf_bytes))


def test_long_body_text_still_produces_one_document_not_a_crash() -> None:
    long_body = "Line of receipt detail. " * 400
    pdf_bytes = build_receipt_pdf(
        _message(body_text=long_body), [], company="Acme Cloud", date="2026-08-01"
    )
    reader = PdfReader(BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1


@pytest.mark.parametrize("missing", ["company", "date"])
def test_missing_extraction_field_is_rejected(missing: str) -> None:
    kwargs = {"company": "Acme Cloud", "date": "2026-08-01"}
    kwargs[missing] = ""
    with pytest.raises(ValueError):
        build_receipt_pdf(_message(), [], **kwargs)  # type: ignore[arg-type]
