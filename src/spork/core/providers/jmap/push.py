"""EventSource push listener (docs/DESIGN.md §6.2 step 3, §8).

`JmapPushTrigger` satisfies `spork.core.sources.base.Trigger`
structurally, so it plugs into `TriggeredSource` exactly like
`ImmediateTrigger` or `IntervalTimer`. Its `wait()` would block on a
live JMAP EventSource connection — real-network work this environment
can't exercise honestly, so it's deliberately NotImplementedError-
stubbed for the same reason as `spork.core.providers.jmap.client.JmapClient` (see
that module's docstring). Reconnect/backoff *scheduling* is already
implemented and tested separately (`spork.core.providers.jmap.backoff`); what's
missing here is the actual listen loop that scheduling would drive.
"""

from __future__ import annotations

from spork.core.providers.jmap.client import JmapClient


class JmapPushTrigger:
    """A Trigger that blocks on a live JMAP EventSource connection.

    Design gap, stated rather than silently missing (docs/DESIGN.md
    §12.2/§12.3): M4's "daemon health" alert triggers include "JMAP
    push disconnected > N minutes," and this class is exactly where
    that timer would live — `wait()` is the one call already on the
    hook for noticing a stalled connection. It stays undesigned for
    the same reason `wait()` itself is a stub: there's no live
    EventSource here to time out on, so a disconnect-timer design
    would be inventing a shape against nothing real to validate it
    against (same "don't fake what isn't there" principle CLAUDE.md
    states directly). Once `wait()` is real, the likely shape is a
    last-event timestamp checked against a deadline on each reconnect
    attempt, firing through the same `PipelineObserver`/`Alerter` path
    `_check_daily_budget_alert()` (`spork.daemon.loop`, §12.3) already
    uses for the sibling daemon-health signal that *could* be built
    honestly — not a new alerting mechanism, just a new caller of the
    existing one, once there's something real for it to observe.
    """

    def __init__(self, client: JmapClient) -> None:
        self._client = client

    def wait(self) -> None:
        raise NotImplementedError(
            "JmapPushTrigger.wait() requires a live JMAP EventSource connection — "
            "not implemented yet, see docs/ROADMAP.md M1"
        )
