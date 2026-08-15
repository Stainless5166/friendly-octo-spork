"""Primary/secondary Source fallback (docs/DESIGN.md §8's "poll-based
fallback when push is unavailable/disconnected").

Expressed generically over the `Source` protocol rather than as
JMAP-specific reconnect plumbing — a push-based primary and a
poll-based secondary are the concrete M1 use case, but this class
itself doesn't know or care which is which.
"""

from __future__ import annotations

from collections.abc import Sequence

from spork.core.models import NormalizedMessage
from spork.core.sources.base import CheckpointedSource, MessageBatch, Source


class FallbackSource:
    """Tries `primary` first; falls back to `secondary` when `primary`
    raises one of `catch`.

    Always tries `primary` again on the *next* poll() call, rather than
    latching onto `secondary` once a fallback happens — a recovered
    connection (JMAP push reconnecting) gets used again automatically,
    with no explicit "switch back" step required anywhere.
    """

    def __init__(
        self,
        primary: Source,
        secondary: Source,
        *,
        catch: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._catch = catch

    def poll(self) -> Sequence[NormalizedMessage]:
        try:
            return self._primary.poll()
        except self._catch:
            return self._secondary.poll()


class CheckpointedFallbackSource:
    """Select between cursor-aware primary and secondary sources."""

    def __init__(
        self,
        primary: CheckpointedSource,
        secondary: CheckpointedSource,
        *,
        catch: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._catch = catch

    def poll_batch(self) -> MessageBatch:
        """Retry primary on every call and preserve candidate checkpoints."""
        try:
            return self._primary.poll_batch()
        except self._catch:
            return self._secondary.poll_batch()

    def poll(self) -> Sequence[NormalizedMessage]:
        """Expose the ordinary Source view for generic consumers."""
        return self.poll_batch().messages
