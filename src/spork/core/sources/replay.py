"""Dependency-free Trigger/ContentFetcher for tests and demos.

Composing these two via `TriggeredSource` gives the "replay a
test/demo file through a for-loop" debug source from docs/DESIGN.md
§9.2 — no bespoke `Source` subclass needed, and no real I/O anywhere,
which is exactly what makes it usable in CI.
"""

from __future__ import annotations

from collections.abc import Sequence

from spork.core.models import NormalizedMessage


class ImmediateTrigger:
    """A Trigger that never waits.

    Correct for anything where "poll now" is the right semantics: unit
    tests, demos, and replaying an already-fetched fixture where
    there's no real "when" to decide.
    """

    def wait(self) -> None:
        return None


class SequenceContentFetcher:
    """Replays a pre-loaded sequence of messages, batch_size at a time.

    Each fetch() call consumes and returns the next batch; once the
    sequence is exhausted, further calls return an empty batch forever
    — the same steady state a live, caught-up source settles into, not
    a distinct "done" signal a caller has to special-case.
    """

    def __init__(self, messages: Sequence[NormalizedMessage], batch_size: int = 1) -> None:
        if batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {batch_size}")
        self._remaining = list(messages)
        self._batch_size = batch_size

    def fetch(self) -> Sequence[NormalizedMessage]:
        batch = self._remaining[: self._batch_size]
        self._remaining = self._remaining[self._batch_size :]
        return batch
