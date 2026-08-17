"""Acceptance tests for spork.core.receipts.archive.save_pdf() (docs/DESIGN.md §9.5).

The write-side counterpart to build_receipt_pdf(): a pure filesystem
write, no PDF construction here (that's pdf.py) and no network I/O.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.receipts.archive import ReceiptArchiveError, save_pdf


def test_saves_bytes_to_a_deterministic_filename_under_output_dir(tmp_path: Path) -> None:
    path = save_pdf(
        b"%PDF-1.4 fake",
        output_dir=tmp_path,
        message_id="msg-1",
        company="Acme Cloud",
        date="2026-08-01",
    )
    assert path.parent == tmp_path
    assert path.read_bytes() == b"%PDF-1.4 fake"


def test_filename_contains_date_company_and_message_id(tmp_path: Path) -> None:
    path = save_pdf(
        b"x",
        output_dir=tmp_path,
        message_id="msg-42",
        company="Acme Cloud",
        date="2026-08-01",
    )
    assert "2026-08-01" in path.name
    assert "acme-cloud" in path.name.lower()
    assert "msg-42" in path.name


def test_company_with_spaces_and_punctuation_is_slugified(tmp_path: Path) -> None:
    path = save_pdf(
        b"x",
        output_dir=tmp_path,
        message_id="msg-1",
        company="New Vendor, Inc.",
        date="2026-08-01",
    )
    assert " " not in path.name
    assert "," not in path.name


def test_creates_output_dir_if_missing(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "receipts"
    path = save_pdf(
        b"x", output_dir=target, message_id="msg-1", company="Acme Cloud", date="2026-08-01"
    )
    assert path.exists()


def test_unwritable_output_dir_raises_one_wrapped_error_type(tmp_path: Path) -> None:
    """A path component that's a plain file, not a directory, blocks
    `mkdir(parents=True)` deterministically regardless of the running
    user's privilege level (unlike chmod-based permission denial, which
    a root-run test suite can't exercise honestly)."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")

    with pytest.raises(ReceiptArchiveError):
        save_pdf(
            b"x",
            output_dir=blocker / "sub",
            message_id="msg-1",
            company="Acme Cloud",
            date="2026-08-01",
        )


def test_two_saves_for_the_same_message_do_not_collide(tmp_path: Path) -> None:
    first = save_pdf(
        b"first", output_dir=tmp_path, message_id="msg-1", company="Acme Cloud", date="2026-08-01"
    )
    second = save_pdf(
        b"second",
        output_dir=tmp_path,
        message_id="msg-2",
        company="Acme Cloud",
        date="2026-08-01",
    )
    assert first != second
    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"second"
