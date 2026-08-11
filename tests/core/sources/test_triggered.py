"""Acceptance tests for composing a Trigger + ContentFetcher into a Source
(docs/DESIGN.md §9.2).

TriggeredSource is exercised against plain stub Trigger/ContentFetcher
objects — never a real timer or JMAP/IMAP connection.
"""

from __future__ import annotations

from spork.core.models import NormalizedMessage
from spork.core.sources.triggered import TriggeredSource


def test_triggered_source_calls_wait_before_fetch(make_message) -> None:
    """poll() must trigger first, then fetch — never the reverse, since
    a real fetcher's result usually depends on the trigger having
    already fired (e.g. a JMAP push's state token)."""
    calls: list[str] = []

    class RecordingTrigger:
        def wait(self) -> None:
            calls.append("wait")

    class RecordingFetcher:
        def fetch(self) -> list[NormalizedMessage]:
            calls.append("fetch")
            return []

    source = TriggeredSource(RecordingTrigger(), RecordingFetcher())
    source.poll()

    assert calls == ["wait", "fetch"]


def test_triggered_source_returns_the_fetchers_result(make_message) -> None:
    """poll() returns exactly what the ContentFetcher produced."""
    expected = [make_message(message_id="msg-1"), make_message(message_id="msg-2")]

    class NoOpTrigger:
        def wait(self) -> None:
            return None

    class FixedFetcher:
        def fetch(self) -> list[NormalizedMessage]:
            return expected

    source = TriggeredSource(NoOpTrigger(), FixedFetcher())

    assert source.poll() == expected
