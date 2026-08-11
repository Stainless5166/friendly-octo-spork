"""An interval-based Trigger (docs/DESIGN.md §8's poll-based fallback,
§9.2's "timer + IMAP" example).

Deliberately not JMAP- or IMAP-specific — this is just "wait N seconds"
as a `Trigger`, composable via `TriggeredSource` with whatever
`ContentFetcher` a given poll-based source needs.
"""

from __future__ import annotations

import time
from collections.abc import Callable


class IntervalTimer:
    """A Trigger that waits a fixed number of seconds between fires.

    `sleep` is injectable (defaults to `time.sleep`) so tests can drive
    this without waiting in real time — the same reason
    `MailboxResolver` takes a plain fetch callable instead of a live
    client.
    """

    def __init__(
        self,
        interval_seconds: float,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError(f"interval_seconds must be > 0, got {interval_seconds}")
        self._interval_seconds = interval_seconds
        self._sleep = sleep

    def wait(self) -> None:
        self._sleep(self._interval_seconds)
