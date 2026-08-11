"""Failure/edge-case tests for the replay ContentFetcher.

Companion to test_replay.py's acceptance tests.
"""

from __future__ import annotations

import pytest

from spork.core.sources.replay import SequenceContentFetcher


def test_sequence_content_fetcher_rejects_non_positive_batch_size(make_message) -> None:
    """batch_size <= 0 can never make progress (0) or means something
    nonsensical (negative) — reject it at construction, not by hanging
    or silently no-op-ing on the first fetch()."""
    with pytest.raises(ValueError, match="batch_size"):
        SequenceContentFetcher([make_message()], batch_size=0)
    with pytest.raises(ValueError, match="batch_size"):
        SequenceContentFetcher([make_message()], batch_size=-1)


def test_sequence_content_fetcher_with_empty_messages_returns_empty_immediately() -> None:
    """An empty fixture behaves like an already-exhausted one, not an error."""
    fetcher = SequenceContentFetcher([], batch_size=5)

    assert fetcher.fetch() == []


def test_sequence_content_fetcher_batch_larger_than_remaining_returns_partial_batch(
    make_message,
) -> None:
    """A batch_size bigger than what's left returns just what's left,
    not an error and not padded/repeated to fill the batch."""
    messages = [make_message(message_id="only-one")]
    fetcher = SequenceContentFetcher(messages, batch_size=100)

    first = fetcher.fetch()
    second = fetcher.fetch()

    assert [m.message_id for m in first] == ["only-one"]
    assert second == []
