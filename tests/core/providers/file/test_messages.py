"""Acceptance tests for the FileProvider messages loader (docs/DESIGN.md §9.3).

Mirrors spork.core.rules.loader's test shape: parsing, empty-input, and
wrapping every failure mode as one clear, catchable error type instead
of letting json/KeyError leak through unwrapped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spork.core.providers.file.messages import MessagesLoadError, load_messages


def test_load_messages_parses_a_valid_json_file(tmp_path: Path) -> None:
    """A well-formed messages.json parses into NormalizedMessage objects
    with the expected fields, in file order."""
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
                    "body_text": "Hi there.",
                },
                {
                    "message_id": "msg-2",
                    "thread_id": "thread-2",
                    "from_address": "b@newsletter.example.com",
                    "from_domain": "newsletter.example.com",
                    "subject": "Weekly digest",
                    "body_text": "News.",
                    "headers": {"List-Unsubscribe": "<mailto:x>"},
                    "mailbox_ids": ["inbox"],
                },
            ]
        )
    )

    messages = load_messages(path)

    assert [m.message_id for m in messages] == ["msg-1", "msg-2"]
    assert messages[1].headers == {"List-Unsubscribe": "<mailto:x>"}
    assert messages[1].mailbox_ids == ("inbox",)


def test_load_messages_returns_empty_list_for_empty_array(tmp_path: Path) -> None:
    """A syntactically valid file containing `[]` is zero messages, not
    an error — an empty fixture is a legitimate starting point."""
    path = tmp_path / "messages.json"
    path.write_text("[]")

    assert load_messages(path) == []


def test_load_messages_raises_for_malformed_json(tmp_path: Path) -> None:
    """Broken JSON syntax is a clear MessagesLoadError, not a raw
    json.JSONDecodeError leaking through unwrapped."""
    path = tmp_path / "messages.json"
    path.write_text("this is not [ valid json")

    with pytest.raises(MessagesLoadError):
        load_messages(path)


def test_load_messages_raises_for_non_array_json(tmp_path: Path) -> None:
    """A file whose top level isn't a JSON array (e.g. a single object)
    is a clear MessagesLoadError, not an unhelpful TypeError further down."""
    path = tmp_path / "messages.json"
    path.write_text(json.dumps({"message_id": "msg-1"}))

    with pytest.raises(MessagesLoadError):
        load_messages(path)


def test_load_messages_raises_for_missing_required_field(tmp_path: Path) -> None:
    """A message object missing a required NormalizedMessage field is a
    clear MessagesLoadError naming the field, not a raw KeyError."""
    path = tmp_path / "messages.json"
    path.write_text(json.dumps([{"message_id": "msg-1"}]))

    with pytest.raises(MessagesLoadError):
        load_messages(path)


def test_load_messages_raises_for_missing_file(tmp_path: Path) -> None:
    """A path that doesn't exist is a clear MessagesLoadError, not a raw
    FileNotFoundError."""
    with pytest.raises(MessagesLoadError):
        load_messages(tmp_path / "does-not-exist.json")
