"""Reconnect backoff scheduling for the JMAP push listener (docs/DESIGN.md §8).

Deliberately not an exponential-backoff *formula* — `config.toml`'s
`polling.reconnect_backoff_seconds` is an explicit list the user
tunes directly (e.g. `[2, 5, 15, 60, 300]`), so this module's only job
is "which entry applies to this attempt", not deriving delays itself.
"""

from __future__ import annotations

from collections.abc import Sequence


def next_delay(schedule: Sequence[float], attempt: int) -> float:
    """Return the reconnect delay (seconds) for the given attempt number.

    `attempt` is 0-indexed (the first retry after a disconnect is
    attempt 0). Once `attempt` runs past the end of `schedule`, the
    delay clamps to the last (longest) entry rather than raising or
    wrapping around — a connection that keeps failing should settle
    into a steady retry cadence forever, not escalate without bound or
    silently start retrying fast again.
    """
    if not schedule:
        raise ValueError("reconnect backoff schedule must not be empty")
    if attempt < 0:
        raise ValueError(f"attempt must be >= 0, got {attempt}")
    index = min(attempt, len(schedule) - 1)
    return schedule[index]
