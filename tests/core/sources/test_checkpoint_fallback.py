"""Acceptance tests for checkpoint-preserving push/poll fallback."""

from collections.abc import Sequence

import pytest

from spork.core.models import NormalizedMessage
from spork.core.providers.jmap.push import JmapPushDisconnectedError
from spork.core.sources.base import MessageBatch
from spork.core.sources.fallback import CheckpointedFallbackSource


class _Source:
    def __init__(self, batches: list[object]) -> None:
        self._batches = batches

    def poll_batch(self) -> MessageBatch:
        batch = self._batches.pop(0)
        if isinstance(batch, Exception):
            raise batch
        if not isinstance(batch, MessageBatch):
            raise TypeError(f"expected MessageBatch, got {type(batch).__name__}")
        return batch

    def poll(self) -> Sequence[NormalizedMessage]:
        return self.poll_batch().messages


def test_checkpoint_fallback_uses_polling_after_push_disconnect() -> None:
    source = CheckpointedFallbackSource(
        _Source([JmapPushDisconnectedError("down")]),
        _Source([MessageBatch(messages=(), checkpoint="state-2")]),
        catch=(JmapPushDisconnectedError,),
    )

    assert source.poll_batch().checkpoint == "state-2"


def test_checkpoint_fallback_retries_push_on_the_next_poll() -> None:
    source = CheckpointedFallbackSource(
        _Source(
            [
                JmapPushDisconnectedError("down"),
                MessageBatch(messages=(), checkpoint="state-3"),
            ]
        ),
        _Source([MessageBatch(messages=(), checkpoint="state-2")]),
        catch=(JmapPushDisconnectedError,),
    )

    assert source.poll_batch().checkpoint == "state-2"
    assert source.poll_batch().checkpoint == "state-3"


def test_checkpoint_fallback_does_not_hide_unconfigured_failures() -> None:
    source = CheckpointedFallbackSource(
        _Source([RuntimeError("bug")]),
        _Source([MessageBatch(messages=(), checkpoint="state-2")]),
        catch=(JmapPushDisconnectedError,),
    )

    with pytest.raises(RuntimeError, match="bug"):
        source.poll_batch()


def test_checkpoint_fallback_exposes_the_plain_source_view() -> None:
    source = CheckpointedFallbackSource(
        _Source([MessageBatch(messages=(), checkpoint="state-1")]),
        _Source([MessageBatch(messages=(), checkpoint="state-2")]),
    )

    assert source.poll() == ()


def test_checkpoint_fallback_propagates_secondary_failures() -> None:
    source = CheckpointedFallbackSource(
        _Source([JmapPushDisconnectedError("down")]),
        _Source([RuntimeError("poll failed")]),
        catch=(JmapPushDisconnectedError,),
    )

    with pytest.raises(RuntimeError, match="poll failed"):
        source.poll_batch()
