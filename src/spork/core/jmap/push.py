"""EventSource push listener (docs/DESIGN.md §6.2 step 3, §8).

`JmapPushTrigger` satisfies `spork.core.sources.base.Trigger`
structurally, so it plugs into `TriggeredSource` exactly like
`ImmediateTrigger` or `IntervalTimer`. Its `wait()` would block on a
live JMAP EventSource connection — real-network work this environment
can't exercise honestly, so it's deliberately NotImplementedError-
stubbed for the same reason as `spork.core.jmap.client.JmapClient` (see
that module's docstring). Reconnect/backoff *scheduling* is already
implemented and tested separately (`spork.core.jmap.backoff`); what's
missing here is the actual listen loop that scheduling would drive.
"""

from __future__ import annotations

from spork.core.jmap.client import JmapClient


class JmapPushTrigger:
    """A Trigger that blocks on a live JMAP EventSource connection."""

    def __init__(self, client: JmapClient) -> None:
        self._client = client

    def wait(self) -> None:
        raise NotImplementedError(
            "JmapPushTrigger.wait() requires a live JMAP EventSource connection — "
            "not implemented yet, see docs/ROADMAP.md M1"
        )
