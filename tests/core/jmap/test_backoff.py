"""Acceptance tests for JMAP push reconnect backoff (docs/DESIGN.md §8).

`polling.reconnect_backoff_seconds` in config.toml is a fixed schedule
(e.g. `[2, 5, 15, 60, 300]`); this covers only spork's own "which delay
applies to this attempt" logic, not any retry/scheduling library.
"""

from __future__ import annotations

from spork.core.jmap.backoff import next_delay


def test_next_delay_returns_schedule_value_for_attempt_in_range() -> None:
    """Attempt N (0-indexed) uses the Nth configured delay."""
    schedule = [2.0, 5.0, 15.0, 60.0, 300.0]

    assert next_delay(schedule, attempt=0) == 2.0
    assert next_delay(schedule, attempt=2) == 15.0


def test_next_delay_clamps_to_final_value_beyond_schedule_length() -> None:
    """Attempts past the end of the schedule stick at the last (longest)
    delay rather than raising or wrapping — a flaky connection should
    settle into a steady retry cadence, not escalate forever."""
    schedule = [2.0, 5.0, 15.0]

    assert next_delay(schedule, attempt=10) == 15.0
