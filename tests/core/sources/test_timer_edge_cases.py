"""Failure/edge-case tests for IntervalTimer.

Companion to test_timer.py's acceptance tests.
"""

from __future__ import annotations

import pytest

from spork.core.sources.timer import IntervalTimer


def test_interval_timer_rejects_non_positive_interval() -> None:
    """An interval of 0 would busy-loop; negative is nonsensical —
    both are rejected at construction, not left to misbehave later."""
    with pytest.raises(ValueError, match="interval_seconds"):
        IntervalTimer(0.0)
    with pytest.raises(ValueError, match="interval_seconds"):
        IntervalTimer(-1.0)
