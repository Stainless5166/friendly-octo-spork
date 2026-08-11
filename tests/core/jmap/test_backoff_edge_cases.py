"""Failure/edge-case tests for reconnect backoff scheduling.

Companion to test_backoff.py's acceptance tests — covers the two
invalid-input shapes a misconfigured `reconnect_backoff_seconds` or a
caller bug could produce.
"""

from __future__ import annotations

import pytest

from spork.core.jmap.backoff import next_delay


def test_next_delay_raises_on_empty_schedule() -> None:
    """An empty schedule is a config error, not "reconnect instantly forever"."""
    with pytest.raises(ValueError, match="empty"):
        next_delay([], attempt=0)


def test_next_delay_raises_on_negative_attempt() -> None:
    """A negative attempt number is a caller bug, not "use the first delay"."""
    with pytest.raises(ValueError, match="attempt"):
        next_delay([2.0, 5.0], attempt=-1)
