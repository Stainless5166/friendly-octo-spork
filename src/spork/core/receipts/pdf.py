"""Combines a receipt message and its attachments into one archival PDF (§9.5).

Pure function: no filesystem I/O (see `spork.core.receipts.archive` for
the "write it somewhere" half) and no network I/O. Lazily imports
pypdf/reportlab -- the optional `spork[receipts]` extra -- so importing
this module never requires them unless a caller actually builds a PDF,
the same lazy-optional-import pattern
`spork.core.llm.clients.litellm._load_completion()` uses for litellm.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from spork.core.models import Attachment, NormalizedMessage


class ReceiptPdfError(Exception):
    """Raised when a receipt PDF can't be built at all -- a missing
    optional dependency. A single malformed attachment does *not*
    raise this: it degrades to a named placeholder page (see
    `_append_attachment`) rather than failing the whole archive over
    one bad attachment.
    """


def _import(module_name: str) -> Any:
    """Import an optional `spork[receipts]` dependency, or fail with a
    clear, actionable error instead of a bare ImportError."""
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise ReceiptPdfError(
            f"build_receipt_pdf requires the optional receipts dependency "
            f"({module_name}); install spork[receipts]"
        ) from exc


def _cover_page_bytes(message: NormalizedMessage, *, company: str, date: str) -> bytes:
    """Render the cover page(s): subject/sender/company/date/tags, then
    the message body. Platypus's flowable layout paginates on its own
    if the body runs long, so this can legitimately be more than one
    page -- that's the "message itself" half of the archive, not just
    a label for the attachments that follow.
    """
    pagesizes = _import("reportlab.lib.pagesizes")
    platypus = _import("reportlab.platypus")
    styles_mod = _import("reportlab.lib.styles")

    styles = styles_mod.getSampleStyleSheet()
    story = [
        platypus.Paragraph(escape(message.subject) or "(no subject)", styles["Title"]),
        platypus.Paragraph(f"From: {escape(message.from_address)}", styles["Normal"]),
        platypus.Paragraph(f"Company: {escape(company)}", styles["Normal"]),
        platypus.Paragraph(f"Date: {escape(date)}", styles["Normal"]),
        platypus.Paragraph(
            f"Tags: receipt, company:{escape(company)}, date:{escape(date)}", styles["Normal"]
        ),
        platypus.Spacer(1, 12),
    ]
    body_lines = (message.body_text or "").splitlines() or [""]
    for line in body_lines:
        story.append(platypus.Paragraph(escape(line) if line else "&nbsp;", styles["Normal"]))

    buf = BytesIO()
    doc = platypus.SimpleDocTemplate(buf, pagesize=pagesizes.letter)
    doc.build(story)
    return buf.getvalue()


def _placeholder_page_bytes(text: str) -> bytes:
    """A one-page note for an attachment this module can't render
    directly -- named and typed, never silently dropped."""
    pagesizes = _import("reportlab.lib.pagesizes")
    canvas_mod = _import("reportlab.pdfgen.canvas")

    buf = BytesIO()
    c = canvas_mod.Canvas(buf, pagesize=pagesizes.letter)
    _, height = pagesizes.letter
    c.drawString(72, height - 100, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def _image_page_bytes(data: bytes) -> bytes:
    """One full page holding a single image attachment, scaled to fit
    the page while preserving aspect ratio."""
    pagesizes = _import("reportlab.lib.pagesizes")
    canvas_mod = _import("reportlab.pdfgen.canvas")
    utils = _import("reportlab.lib.utils")

    page_width, page_height = pagesizes.letter
    margin = 36
    max_width = page_width - 2 * margin
    max_height = page_height - 2 * margin

    image = utils.ImageReader(BytesIO(data))
    img_width, img_height = image.getSize()
    scale = min(max_width / img_width, max_height / img_height, 1.0)
    draw_width, draw_height = img_width * scale, img_height * scale

    buf = BytesIO()
    c = canvas_mod.Canvas(buf, pagesize=pagesizes.letter)
    c.drawImage(
        image,
        (page_width - draw_width) / 2,
        (page_height - draw_height) / 2,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
    )
    c.showPage()
    c.save()
    return buf.getvalue()


def _append_pages(writer: Any, pdf_bytes: bytes) -> None:
    pypdf_mod = _import("pypdf")
    for page in pypdf_mod.PdfReader(BytesIO(pdf_bytes)).pages:
        writer.add_page(page)


def _append_attachment(writer: Any, attachment: Attachment) -> None:
    """Place one attachment's page(s) onto the writer, in order.

    An existing PDF is merged page-for-page; an image becomes one full
    page; anything else -- or anything that fails to parse as what its
    content type claims -- becomes a placeholder page naming it, so an
    attachment spork can't render is still accounted for, never
    silently dropped from the archive.
    """
    if attachment.content_type == "application/pdf":
        try:
            _append_pages(writer, attachment.data)
            return
        except ReceiptPdfError:
            raise
        except Exception:  # noqa: BLE001 - any parse failure degrades to a placeholder
            pass
    elif attachment.content_type.startswith("image/"):
        try:
            _append_pages(writer, _image_page_bytes(attachment.data))
            return
        except ReceiptPdfError:
            raise
        except Exception:  # noqa: BLE001 - any decode failure degrades to a placeholder
            pass

    _append_pages(
        writer,
        _placeholder_page_bytes(
            f"Attachment not rendered: {attachment.filename} ({attachment.content_type})"
        ),
    )


def build_receipt_pdf(
    message: NormalizedMessage,
    attachments: Sequence[Attachment],
    *,
    company: str,
    date: str,
) -> bytes:
    """Build one archival PDF: a cover page (subject/sender/company/date/
    tags + the message body) followed by every attachment in order.

    No attachments still produces a valid one-section PDF from the
    cover content alone -- the "or the message itself" half of the
    feature request, not a degenerate case.
    """
    if not company:
        raise ValueError("build_receipt_pdf requires a non-empty company")
    if not date:
        raise ValueError("build_receipt_pdf requires a non-empty date")

    pypdf_mod = _import("pypdf")
    writer = pypdf_mod.PdfWriter()
    _append_pages(writer, _cover_page_bytes(message, company=company, date=date))
    for attachment in attachments:
        _append_attachment(writer, attachment)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()
