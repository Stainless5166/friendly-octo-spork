"""Writes a built receipt PDF to the configured archive directory (§9.5).

The write-side counterpart to `spork.core.receipts.pdf.build_receipt_pdf()`
-- deliberately separate, same "building bytes" vs. "writing them
somewhere" split `spork.core.rules.schema`/`spork.core.actions.executor`
already draw between deciding an action and applying it.
"""

from __future__ import annotations

import re
from pathlib import Path


class ReceiptArchiveError(Exception):
    """Raised when a receipt PDF can't be written to disk.

    One wrapped error type for whatever the underlying filesystem call
    raised (a read-only directory, a full disk), same one-error-type-
    per-module-boundary convention as `RulesLoadError`/`ProviderLoadError`/
    `ActionExecutionError`. Callers (the pipeline stage, once wired)
    catch this and leave the message unmarked-processed rather than
    letting it propagate as a raw traceback.
    """


def _slugify(value: str) -> str:
    """Reduce a value to filesystem- and URL-safe lowercase segments,
    joined by single hyphens -- deliberately not a general slug
    library: the only inputs here are a company name and a message id,
    both already short plain text."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def save_pdf(
    pdf_bytes: bytes,
    *,
    output_dir: Path,
    message_id: str,
    company: str,
    date: str,
) -> Path:
    """Write `pdf_bytes` under `output_dir`, creating it if needed.

    Filename is `{date}-{company-slug}-{message_id-slug}.pdf` --
    sortable by date first, human-identifiable by company, and unique
    per message even when company/date repeat (two receipts from the
    same company on the same day never collide).
    """
    target_dir = Path(output_dir)
    filename = f"{date}-{_slugify(company)}-{_slugify(message_id)}.pdf"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
        path.write_bytes(pdf_bytes)
    except OSError as exc:
        raise ReceiptArchiveError(f"could not save receipt PDF to {target_dir}: {exc}") from exc
    return path
