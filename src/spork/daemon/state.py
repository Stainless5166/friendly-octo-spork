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


@dataclass(frozen=True, slots=True)
class PendingAuditEvent:
    """One control-plane audit entry queued by an `IpcServer` handler,
    not yet written (docs/DESIGN.md §6.2.2/§7.4, M7).

    A first-draft design had `pause`/`resume` `await
    asyncio.to_thread(state_db.write_control_plane_audit_entry, ...)`
    directly — that doesn't actually serialize against
    `_run_message_loop()`'s own in-flight `to_thread(process_message,
    ...)` call, since two independent `to_thread()` calls from two
    different coroutines can still race the same `state_db` connection
    object. Queuing here instead means the one code path that already
    safely, sequentially owns every `state_db` access
    (`_run_message_loop()`) is the only thing that ever writes one —
    `event`/`detail_json` are exactly `write_control_plane_audit_entry()`'s
    own parameters, minus `ts` (stamped at drain time, by
    `_run_message_loop()`'s own clock, not at enqueue time).
    """

    event: str
    detail_json: str | None


@dataclass
class DaemonState:
    """`paused`: toggled by the `pause`/`resume` IPC commands, read by
    `_run_message_loop()` each cycle. `started_at`: set once at
    `run_daemon()` startup, never mutated after — `spork status`'s
    uptime field. `budget_exhausted_alert_date`: the ISO date
    (`YYYY-MM-DD`) the daily-budget-exhausted daemon-health alert last
    fired on, or `None` if it hasn't fired today — a date-equality
    guard rather than a boolean flag, so the alert self-resets across
    midnight without any special-cased reset logic (docs/DESIGN.md
    §12.3). `pending_control_plane_events`: queued by `pause`/`resume`
    (M7, §6.2.2/§7.4), drained once per `_run_message_loop()` iteration
    — see `PendingAuditEvent`'s own docstring for why this exists
    rather than a direct write from the IPC handler."""

    paused: bool = False
    started_at: str = ""
    budget_exhausted_alert_date: str | None = None
    pending_control_plane_events: list[PendingAuditEvent] = field(default_factory=list)


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
