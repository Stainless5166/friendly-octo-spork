"""SQLite-backed state store: push cursor + processed-messages (§7.4).

A single file, WAL mode, no external DB dependency — sporkd is a
single-process daemon, so there's no concurrent-writer story to design
for yet (docs/DESIGN.md §7.4).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

# CREATE TABLE IF NOT EXISTS makes opening a fresh vs. an existing DB
# file the same code path — no separate "run migrations" step exists
# yet. Column sets match docs/DESIGN.md §7.4 exactly; rule_stats/
# llm_usage are added by the milestones that actually need them.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS push_cursor (
    account_id TEXT PRIMARY KEY,
    state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_messages (
    jmap_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    received_at TEXT,
    tier_reached TEXT,
    verdict_json TEXT,
    action_taken TEXT,
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    jmap_id TEXT NOT NULL,
    event TEXT NOT NULL,
    detail_json TEXT
);

CREATE TABLE IF NOT EXISTS llm_usage (
    date TEXT PRIMARY KEY,
    calls INTEGER NOT NULL DEFAULT 0,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One row from the audit_log table — the human-readable trail
    `spork logs` (M5) reads from, and what §11's "why did this happen
    to this email" answer ultimately comes from."""

    id: int
    ts: str
    jmap_id: str
    event: str
    detail_json: str | None


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """One day's Tier 2 (Claude) call volume — what §10.4's
    `daily_call_budget` check reads, and what `spork status` (M5)
    will surface as actual spend."""

    date: str
    calls: int
    tokens_in: int
    tokens_out: int


class StateDB:
    """Owns the on-disk SQLite connection and the two M1 tables.

    A thin wrapper, not an ORM — the daemon's state needs are small
    enough that hand-written SQL stays more readable than an
    abstraction layer over it would be.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> StateDB:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # --- push cursor: where the daemon left off ---------------------

    def get_cursor(self, account_id: str) -> str | None:
        """Return the last JMAP `state` string seen for `account_id`,
        or None if this account has never been polled/pushed to —
        callers treat None as "fetch everything since the beginning"."""
        row = self._conn.execute(
            "SELECT state FROM push_cursor WHERE account_id = ?", (account_id,)
        ).fetchone()
        return row[0] if row else None

    def set_cursor(self, account_id: str, state: str) -> None:
        """Persist the latest JMAP `state` for `account_id`, so a
        restart resumes from here instead of re-scanning the mailbox."""
        self._conn.execute(
            "INSERT INTO push_cursor (account_id, state) VALUES (?, ?) "
            "ON CONFLICT(account_id) DO UPDATE SET state = excluded.state",
            (account_id, state),
        )
        self._conn.commit()

    # --- processed messages: what the daemon has already acted on ---

    def has_processed(self, jmap_id: str) -> bool:
        """True if `jmap_id` has already been run through the pipeline.

        The idempotency check M2's action executor consults before
        acting — a message is only ever acted on once unless a manual
        `spork reclassify` forces it (docs/DESIGN.md §11).
        """
        row = self._conn.execute(
            "SELECT 1 FROM processed_messages WHERE jmap_id = ?", (jmap_id,)
        ).fetchone()
        return row is not None

    def mark_processed(
        self,
        jmap_id: str,
        *,
        thread_id: str,
        processed_at: str,
        received_at: str | None = None,
        tier_reached: str | None = None,
        verdict_json: str | None = None,
        action_taken: str | None = None,
    ) -> None:
        """Record that `jmap_id` has been processed.

        Re-marking an already-processed message overwrites its record
        rather than erroring — that's exactly what `spork reclassify`
        needs: forcing a message back through the pipeline and updating
        its stored outcome.
        """
        self._conn.execute(
            "INSERT INTO processed_messages "
            "(jmap_id, thread_id, received_at, tier_reached, verdict_json, "
            "action_taken, processed_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(jmap_id) DO UPDATE SET "
            "thread_id = excluded.thread_id, received_at = excluded.received_at, "
            "tier_reached = excluded.tier_reached, verdict_json = excluded.verdict_json, "
            "action_taken = excluded.action_taken, processed_at = excluded.processed_at",
            (
                jmap_id,
                thread_id,
                received_at,
                tier_reached,
                verdict_json,
                action_taken,
                processed_at,
            ),
        )
        self._conn.commit()

    # --- audit log: the human-readable "why did this happen" trail --

    def write_audit_entry(
        self,
        *,
        ts: str,
        jmap_id: str,
        event: str,
        detail_json: str | None = None,
    ) -> None:
        """Append one audit log entry. Append-only — audit entries are
        never updated or overwritten, unlike processed_messages."""
        self._conn.execute(
            "INSERT INTO audit_log (ts, jmap_id, event, detail_json) VALUES (?, ?, ?, ?)",
            (ts, jmap_id, event, detail_json),
        )
        self._conn.commit()

    def get_audit_entries(self, *, jmap_id: str | None = None) -> list[AuditEntry]:
        """Return audit entries oldest-first, optionally filtered to
        one message's `jmap_id`."""
        if jmap_id is None:
            rows = self._conn.execute(
                "SELECT id, ts, jmap_id, event, detail_json FROM audit_log ORDER BY id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, ts, jmap_id, event, detail_json FROM audit_log "
                "WHERE jmap_id = ? ORDER BY id",
                (jmap_id,),
            ).fetchall()
        return [AuditEntry(*row) for row in rows]

    # --- llm_usage: daily Tier 2 call volume, for the budget check ---

    def record_llm_call(self, date: str, *, tokens_in: int, tokens_out: int) -> None:
        """Record one Tier 2 call against `date` (accumulates onto any
        existing row for that date rather than overwriting it — a
        day's second call adds to its first, it doesn't replace it).

        Rejects negative token counts eagerly: SQLite has no opinion on
        an INTEGER column's sign, so an unguarded caller bug (e.g. a
        miscalculated token delta) could otherwise silently corrupt a
        day's running total instead of failing where the bad value
        originated.
        """
        if tokens_in < 0:
            raise ValueError(f"tokens_in must not be negative, got {tokens_in}")
        if tokens_out < 0:
            raise ValueError(f"tokens_out must not be negative, got {tokens_out}")
        self._conn.execute(
            "INSERT INTO llm_usage (date, calls, tokens_in, tokens_out) "
            "VALUES (?, 1, ?, ?) "
            "ON CONFLICT(date) DO UPDATE SET "
            "calls = calls + 1, "
            "tokens_in = tokens_in + excluded.tokens_in, "
            "tokens_out = tokens_out + excluded.tokens_out",
            (date, tokens_in, tokens_out),
        )
        self._conn.commit()

    def get_llm_usage(self, date: str) -> LLMUsage:
        """Return `date`'s recorded Tier 2 call volume.

        Never returns None — a date with no `record_llm_call()` yet is
        `LLMUsage(date, calls=0, tokens_in=0, tokens_out=0)`, so a
        caller (§10.4's budget check) never special-cases "never
        called today" separately from "called zero times today."
        """
        row = self._conn.execute(
            "SELECT calls, tokens_in, tokens_out FROM llm_usage WHERE date = ?", (date,)
        ).fetchone()
        if row is None:
            return LLMUsage(date=date, calls=0, tokens_in=0, tokens_out=0)
        calls, tokens_in, tokens_out = row
        return LLMUsage(date=date, calls=calls, tokens_in=tokens_in, tokens_out=tokens_out)
