"""Acceptance tests for the FileProvider attachments loader (docs/DESIGN.md §9.5, M10).

Mirrors spork.core.providers.file.messages's test shape: parsing,
empty-input, and one clear catchable error type instead of letting
json/KeyError/base64 errors leak through unwrapped.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from spork.core.providers.file.attachments import AttachmentsLoadError, load_attachments


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_load_attachments_parses_attachments_keyed_by_message_id(tmp_path: Path) -> None:
    path = tmp_path / "messages.json"
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "Receipt",
                    "body_text": "Thanks.",
                    "attachments": [
                        {
                            "filename": "invoice.pdf",
                            "content_type": "application/pdf",
                            "data_base64": _b64(b"%PDF-1.4 fake"),
                        }
                    ],
                },
                {
                    "message_id": "msg-2",
                    "thread_id": "thread-2",
                    "from_address": "b@example.com",
                    "from_domain": "example.com",
                    "subject": "No attachments",
                    "body_text": "Hi.",
                },
            ]
        )
    )

    attachments = load_attachments(path)

    assert [a.filename for a in attachments["msg-1"]] == ["invoice.pdf"]
    assert attachments["msg-1"][0].content_type == "application/pdf"
    assert attachments["msg-1"][0].data == b"%PDF-1.4 fake"


def test_a_message_with_no_attachments_key_maps_to_an_empty_list(tmp_path: Path) -> None:
    path = tmp_path / "messages.json"
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "Hello",
                    "body_text": "Hi.",
                }
            ]
        )
    )

    attachments = load_attachments(path)

    assert attachments["msg-1"] == []


def test_a_message_can_have_multiple_attachments_in_order(tmp_path: Path) -> None:
    path = tmp_path / "messages.json"
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "Receipt",
                    "body_text": "Thanks.",
                    "attachments": [
                        {
                            "filename": "a.pdf",
                            "content_type": "application/pdf",
                            "data_base64": _b64(b"first"),
                        },
                        {
                            "filename": "b.png",
                            "content_type": "image/png",
                            "data_base64": _b64(b"second"),
                        },
                    ],
                }
            ]
        )
    )

    attachments = load_attachments(path)

    assert [a.filename for a in attachments["msg-1"]] == ["a.pdf", "b.png"]
    assert attachments["msg-1"][0].data == b"first"
    assert attachments["msg-1"][1].data == b"second"


def test_missing_file_raises_load_error(tmp_path: Path) -> None:
    with pytest.raises(AttachmentsLoadError):
        load_attachments(tmp_path / "does-not-exist.json")


def test_invalid_base64_raises_load_error(tmp_path: Path) -> None:
    path = tmp_path / "messages.json"
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "Receipt",
                    "body_text": "Thanks.",
                    "attachments": [
                        {
                            "filename": "invoice.pdf",
                            "content_type": "application/pdf",
                            "data_base64": "not valid base64!!",
                        }
                    ],
                }
            ]
        )
    )

    with pytest.raises(AttachmentsLoadError):
        load_attachments(path)


def test_attachment_missing_a_required_field_raises_load_error(tmp_path: Path) -> None:
    path = tmp_path / "messages.json"
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": "msg-1",
                    "thread_id": "thread-1",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": "Receipt",
                    "body_text": "Thanks.",
                    "attachments": [{"filename": "invoice.pdf"}],  # missing content_type/data
                }
            ]
        )
    )

    with pytest.raises(AttachmentsLoadError):
        load_attachments(path)
