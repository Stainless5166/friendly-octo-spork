"""Failure/edge-case tests for TriggeredSource.

Companion to test_triggered.py's acceptance tests.
"""

from __future__ import annotations

from spork.core.models import NormalizedMessage
from spork.core.sources.triggered import TriggeredSource


def test_triggered_source_re_triggers_on_every_poll_call(make_message) -> None:
    """Each poll() call waits again, not just the first one — a Source
    that only triggered once would silently stop noticing new content
    after its first fetch."""
    wait_calls = 0

    class CountingTrigger:
        def wait(self) -> None:
            nonlocal wait_calls
            wait_calls += 1

    class EmptyFetcher:
        def fetch(self) -> list[NormalizedMessage]:
            return []

    source = TriggeredSource(CountingTrigger(), EmptyFetcher())

    source.poll()
    source.poll()
    source.poll()

    assert wait_calls == 3
