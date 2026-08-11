"""Failure/edge-case tests for spork.core.providers.file.messages.load_messages().

Companion to test_messages.py's acceptance tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spork.core.providers.file.messages import MessagesLoadError, load_messages


def test_load_messages_raises_when_an_entry_is_not_an_object(tmp_path: Path) -> None:
    """An array entry that isn't itself a JSON object (e.g. a bare
    string) is a clear MessagesLoadError naming the offending index,
    not an unhelpful TypeError from attribute access further down."""
    path = tmp_path / "messages.json"
    path.write_text(json.dumps(["not-an-object"]))

    with pytest.raises(MessagesLoadError):
        load_messages(path)


def test_load_messages_defaults_headers_and_mailbox_ids_when_omitted(tmp_path: Path) -> None:
    """headers/mailbox_ids are optional per message — omitting them
    produces NormalizedMessage's own empty defaults, not a load error."""
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

    messages = load_messages(path)

    assert messages[0].headers == {}
    assert messages[0].mailbox_ids == ()


def test_load_messages_ignores_unknown_fields_on_an_entry(tmp_path: Path) -> None:
    """An entry carrying a field NormalizedMessage doesn't have (e.g. a
    fixture author's scratch note) is loaded, not rejected — messages.py
    only pulls the fields it knows about, unlike rules.schema's
    extra="forbid" (a JSON message fixture isn't hand-edited config the
    same way rules.toml is, so silent-ignore is the right default here)."""
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
                    "note": "scratch fixture, ignore",
                }
            ]
        )
    )

    messages = load_messages(path)

    assert messages[0].message_id == "msg-1"


def test_load_messages_accepts_a_str_path(tmp_path: Path) -> None:
    """A str path works the same as a Path — load_messages shouldn't
    force every caller to wrap its argument first."""
    path = tmp_path / "messages.json"
    path.write_text("[]")

    assert load_messages(str(path)) == []
