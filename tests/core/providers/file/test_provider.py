"""Acceptance tests for FileProvider, the local-file Adapter (docs/DESIGN.md §9.3).

Unlike JmapProvider (still NotImplementedError stubs pending a live
Fastmail session), FileProvider has no live-network blocker at all —
it's a second, fully real Provider implementation, and these tests
confirm the Provider/adapter abstraction actually holds for a backend
other than JMAP: build_source() really replays messages, and
build_action_applier() really records applied actions.
"""

from __future__ import annotations

import json
from pathlib import Path

from spork.core.providers.file.provider import FileProvider

from spork.core.rules.schema import Action
from spork.core.sources.triggered import TriggeredSource


def _write_messages(path: Path) -> None:
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
                    "from_address": "b@example.com",
                    "from_domain": "example.com",
                    "subject": "Hi again",
                    "body_text": "More text.",
                },
            ]
        )
    )


def test_build_source_returns_a_triggered_source(tmp_path: Path) -> None:
    """build_source() composes an ImmediateTrigger + SequenceContentFetcher
    via TriggeredSource — the same generic composition any Source
    consumer expects (docs/DESIGN.md §9.2), not a bespoke shape."""
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")

    source = provider.build_source()

    assert isinstance(source, TriggeredSource)


def test_source_poll_replays_every_message_then_settles_empty(tmp_path: Path) -> None:
    """The composed Source's first poll() returns every message in the
    file; once exhausted it settles into returning nothing, same as a
    live source that's caught up — proving the read side is real, not
    a placeholder."""
    messages_path = tmp_path / "messages.json"
    _write_messages(messages_path)
    provider = FileProvider(messages_path, tmp_path / "actions.jsonl")
    source = provider.build_source()

    first = source.poll()
    second = source.poll()

    assert [m.message_id for m in first] == ["msg-1", "msg-2"]
    assert second == []


def test_build_action_applier_returns_something_that_can_apply(
    tmp_path: Path, make_message
) -> None:
    """build_action_applier() returns an object satisfying ActionApplier
    (has a working .apply() method) — the write half of the Provider
    contract, per docs/DESIGN.md §9.3."""
    provider = FileProvider(tmp_path / "messages.json", tmp_path / "actions.jsonl")
    applier = provider.build_action_applier()

    applier.apply(make_message(message_id="msg-1"), Action(type="move", mailbox="Reading"))

    assert (tmp_path / "actions.jsonl").exists()


def test_action_applier_appends_one_jsonl_entry_per_apply_call(
    tmp_path: Path, make_message
) -> None:
    """Two apply() calls append two JSON-lines entries, in order, each
    recording the message and action involved — an inspectable,
    genuine record of what would have happened, not a silent no-op."""
    log_path = tmp_path / "actions.jsonl"
    provider = FileProvider(tmp_path / "messages.json", log_path)
    applier = provider.build_action_applier()

    applier.apply(make_message(message_id="msg-1"), Action(type="move", mailbox="Reading"))
    applier.apply(make_message(message_id="msg-2"), Action(type="tag", mailbox="Urgent"))

    lines = log_path.read_text().splitlines()
    entries = [json.loads(line) for line in lines]
    assert [e["message_id"] for e in entries] == ["msg-1", "msg-2"]
    assert entries[0]["action_type"] == "move"
    assert entries[0]["mailbox"] == "Reading"
    assert entries[1]["action_type"] == "tag"
