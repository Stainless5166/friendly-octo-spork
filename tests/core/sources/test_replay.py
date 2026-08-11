"""Acceptance tests for the replay/debug source pieces (docs/DESIGN.md §9.2).

ImmediateTrigger + SequenceContentFetcher exist to compose (via
TriggeredSource) into the "replay a test/demo file through a for-loop"
debug source — no bespoke Source class needed for that case.
"""

from __future__ import annotations

from spork.core.sources.replay import ImmediateTrigger, SequenceContentFetcher


def test_immediate_trigger_never_blocks() -> None:
    """wait() returns immediately — no sleeping, no I/O, no side effects."""
    trigger = ImmediateTrigger()

    assert trigger.wait() is None


def test_sequence_content_fetcher_returns_messages_in_batches(make_message) -> None:
    """Each fetch() call returns up to batch_size messages, in order,
    consuming them — the "for loop" part of the debug source."""
    messages = [make_message(message_id=f"msg-{i}") for i in range(3)]
    fetcher = SequenceContentFetcher(messages, batch_size=2)

    first_batch = fetcher.fetch()
    second_batch = fetcher.fetch()

    assert [m.message_id for m in first_batch] == ["msg-0", "msg-1"]
    assert [m.message_id for m in second_batch] == ["msg-2"]


def test_sequence_content_fetcher_returns_empty_once_exhausted(make_message) -> None:
    """Once every message has been returned, further fetch() calls
    return empty forever — the same steady state a live source settles
    into once it's caught up, not an error."""
    fetcher = SequenceContentFetcher([make_message()], batch_size=1)

    fetcher.fetch()

    assert fetcher.fetch() == []
    assert fetcher.fetch() == []
