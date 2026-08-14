"""Acceptance tests for cursor-aware source contracts."""

from collections.abc import Sequence

from spork.core.models import NormalizedMessage
from spork.core.sources.base import CheckpointedSource, MessageBatch


class _FixtureCheckpointedSource:
    def poll_batch(self) -> MessageBatch:
        return MessageBatch(messages=(), checkpoint="state-1")


def test_message_batch_holds_messages_and_a_candidate_checkpoint() -> None:
    batch = MessageBatch(messages=(), checkpoint="state-1")

    assert batch.messages == ()
    assert batch.checkpoint == "state-1"


def test_checkpointed_source_is_structurally_distinct_from_plain_source() -> None:
    source = _FixtureCheckpointedSource()

    assert isinstance(source, CheckpointedSource)
    assert source.poll_batch().checkpoint == "state-1"


def test_message_batch_accepts_an_empty_checkpoint_for_non_cursor_sources() -> None:
    messages: Sequence[NormalizedMessage] = ()

    assert MessageBatch(messages=messages, checkpoint=None).checkpoint is None
