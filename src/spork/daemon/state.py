"""DaemonState/RulesState: mutable state shared by the loop + IPC handlers (docs/DESIGN.md §6.2.2).

Not frozen — unlike every other dataclass in `spork.core`, these are
genuinely mutable. `DaemonState`'s fields are only ever touched from
coroutine code (`_run_message_loop()`'s own control flow, an
`IpcServer` handler) — never from inside a `to_thread()`-wrapped call
— so asyncio's single-thread-at-a-time coroutine scheduling makes them
safe with no lock, by construction, not by convention. `StateDB`
access deliberately stays out of here (see docs/DESIGN.md §6.2.2's
note on why `spork status` doesn't report LLM spend yet).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from spork.core.rules.schema import Rule


@dataclass
class DaemonState:
    """`paused`: toggled by the `pause`/`resume` IPC commands, read by
    `_run_message_loop()` each cycle. `started_at`: set once at
    `run_daemon()` startup, never mutated after — `spork status`'s
    uptime field."""

    paused: bool = False
    started_at: str = ""


@dataclass
class RulesState:
    """The currently-effective rules, reassignable by the `reload` IPC
    command without restarting `sporkd` (docs/DESIGN.md §6.2.2/§7.5).

    The `reload` handler replaces `.rules` wholesale with a fresh
    `load_rules()` result — never mutates the existing list in place —
    and `_run_message_loop()` reads `.rules` fresh at the top of every
    poll iteration rather than capturing it once. That combination is
    what makes this safe without a lock, the same way `DaemonState` is:
    a single attribute reassignment is atomic under CPython's GIL, and
    an in-flight `to_thread(process_message, ...)` call already holds
    its own list reference as an ordinary argument, so it finishes
    against whichever rules were current when it started.
    """

    rules: Sequence[Rule] = field(default_factory=list)
