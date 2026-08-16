"""Acceptance tests for FileProvider.query_messages() (docs/ROADMAP.md M8).

Proves BackfillProvider generalizes beyond JMAP the same way Provider
itself does (§9.3, M1b) — pages through the fixture file in-process,
no live network, no server-side query to delegate to.
"""

from __future__ import annotations

import json
from pathlib import Path

from spork.core.providers.base import BackfillPage, BackfillProvider
from spork.core.providers.file.provider import FileProvider


def _write_messages(path: Path, count: int) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "message_id": f"msg-{i}",
                    "thread_id": f"thread-{i}",
                    "from_address": "a@example.com",
                    "from_domain": "example.com",
                    "subject": f"Subject {i}",
                    "body_text": "Body.",
                }
                for i in range(count)
            ]
        )
    )


def test_provider_satisfies_the_backfill_provider_protocol(tmp_path: Path) -> None:
    provider = FileProvider(tmp_path / "messages.json", tmp_path / "actions.jsonl")

    assert isinstance(provider, BackfillProvider)


def test_query_messages_returns_a_windowed_page(tmp_path: Path) -> None:
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path, count=5)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")

    page = provider.query_messages(position=0, limit=2)

    assert isinstance(page, BackfillPage)
    assert [m.message_id for m in page.messages] == ["msg-0", "msg-1"]
    assert page.position == 0
    assert page.total == 5
    assert page.has_more is True


def test_query_messages_has_more_false_on_the_last_page(tmp_path: Path) -> None:
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path, count=5)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")

    page = provider.query_messages(position=4, limit=2)

    assert [m.message_id for m in page.messages] == ["msg-4"]
    assert page.has_more is False


def test_query_messages_unread_only_is_accepted_but_has_no_filter_to_apply(
    tmp_path: Path,
) -> None:
    """A fixture file has no "seen" state — unread_only=True still returns
    every message rather than silently misrepresenting what it filtered."""
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path, count=3)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")

    page = provider.query_messages(unread_only=True, position=0, limit=50)

    assert len(page.messages) == 3
