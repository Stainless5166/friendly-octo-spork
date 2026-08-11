"""Spec tests for the JMAP EventSource push Trigger (docs/ROADMAP.md M1),
catching its deliberate NotImplementedError placeholder.

See tests/core/providers/jmap/test_client.py's module docstring for
why this is a NotImplementedError-catching test rather than xfail:
wait() would block on a live JMAP EventSource connection, which isn't
something this environment can exercise honestly. Reconnect/backoff
scheduling itself is already implemented and tested separately
(spork.core.providers.jmap.backoff) — what's missing here is just the
actual listen loop.
"""

from __future__ import annotations

import pytest

from spork.core.providers.jmap.client import JmapClient
from spork.core.providers.jmap.push import JmapPushTrigger
from spork.core.sources.triggered import TriggeredSource


def test_wait_raises_not_implemented() -> None:
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")
    trigger = JmapPushTrigger(client)

    with pytest.raises(NotImplementedError):
        trigger.wait()


def test_composes_into_triggered_source_like_any_other_trigger() -> None:
    """JmapPushTrigger satisfies the same Trigger contract as
    ImmediateTrigger/IntervalTimer — plugging it into TriggeredSource
    "just works" structurally, even though wait() itself still raises."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    class UnusedFetcher:
        def fetch(self) -> list[object]:
            raise AssertionError("fetch() should never run — wait() raises first")

    source = TriggeredSource(JmapPushTrigger(client), UnusedFetcher())

    with pytest.raises(NotImplementedError):
        source.poll()
