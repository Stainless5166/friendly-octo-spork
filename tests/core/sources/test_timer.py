"""Acceptance tests for interval-based polling (docs/DESIGN.md §9.2,
§8's poll-based fallback).

IntervalTimer is exercised with an injected fake sleep function — never
a real clock — so these tests run instantly and deterministically.
"""

from __future__ import annotations

from spork.core.sources.timer import IntervalTimer


def test_interval_timer_sleeps_for_the_configured_interval() -> None:
    """wait() sleeps for exactly the configured number of seconds."""
    slept: list[float] = []
    timer = IntervalTimer(30.0, sleep=slept.append)

    timer.wait()

    assert slept == [30.0]


def test_interval_timer_waits_again_on_every_call() -> None:
    """Each wait() call sleeps again — a timer that only fired once
    would silently stop polling after the first cycle."""
    slept: list[float] = []
    timer = IntervalTimer(5.0, sleep=slept.append)

    timer.wait()
    timer.wait()
    timer.wait()

    assert slept == [5.0, 5.0, 5.0]
