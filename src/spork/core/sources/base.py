"""The three contracts message acquisition is built from (docs/DESIGN.md §9.2).

Kept as three separate, minimal Protocols rather than one interface so
a concrete Source can implement `Source` directly when trigger and
fetch are naturally fused (JMAP push: the state token that tells you
*when* is exactly the argument the fetch call needs), or get built for
free by composing an independent `Trigger` and `ContentFetcher`
(`spork.core.sources.triggered.TriggeredSource`) when they aren't.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from spork.core.models import NormalizedMessage


@dataclass(frozen=True, slots=True)
class MessageBatch:
    """Messages plus an optional source state safe to acknowledge later."""

    messages: Sequence[NormalizedMessage]
    checkpoint: str | None = None


@runtime_checkable
class CheckpointedSource(Protocol):
    """A source whose state advances only after daemon processing succeeds."""

    def poll_batch(self) -> MessageBatch:
        """Return messages and a candidate checkpoint for this batch."""
        ...

    def poll(self) -> Sequence[NormalizedMessage]:
        """Remain usable anywhere a plain Source is accepted."""
        ...


class Trigger(Protocol):
    """Decides *when* to fetch again — knows nothing about content."""

    def wait(self) -> None:
        """Block until it's time to fetch again.

        A push-based trigger blocks on its connection; a timer sleeps
        its interval; a trigger meant for tests/demos can return
        immediately. Implementations own their own blocking semantics
        entirely — this contract only promises "returns when it's
        time," not how long that takes or why.
        """
        ...


class ContentFetcher(Protocol):
    """Decides *what* to return once triggered — knows nothing about timing."""

    def fetch(self) -> Sequence[NormalizedMessage]:
        """Return whatever new messages exist right now.

        An empty sequence is a normal, expected result (nothing new
        since last time), not an error — callers should treat it as
        "still caught up," never as "something went wrong."
        """
        ...


class Source(Protocol):
    """What the rest of the pipeline actually pulls from."""

    def poll(self) -> Sequence[NormalizedMessage]:
        """Trigger once, then return whatever messages that produced."""
        ...
