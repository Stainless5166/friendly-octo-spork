"""DaemonState: the mutable state the message loop and IPC handlers share (docs/DESIGN.md §6.2.2).

Not frozen — unlike every other dataclass in `spork.core`, this one is
genuinely mutable. Both fields are only ever touched from coroutine
code (`_run_message_loop()`'s own control flow, an `IpcServer`
handler) — never from inside a `to_thread()`-wrapped call — so
asyncio's single-thread-at-a-time coroutine scheduling makes them safe
with no lock, by construction, not by convention. `StateDB` access
deliberately stays out of here (see docs/DESIGN.md §6.2.2's note on
why `spork status` doesn't report LLM spend yet).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DaemonState:
    """`paused`: toggled by the `pause`/`resume` IPC commands, read by
    `_run_message_loop()` each cycle. `started_at`: set once at
    `run_daemon()` startup, never mutated after — `spork status`'s
    uptime field."""

    paused: bool = False
    started_at: str = ""
