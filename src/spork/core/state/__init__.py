"""Persistent daemon state (docs/DESIGN.md §7.4).

The only state spork keeps across restarts: where it left off (the
push cursor) and what it's already acted on (processed_messages, for
idempotency). Deliberately not a home for anything derived/rebuildable
— audit_log and llm_usage (also §7.4) landed with the milestones that
actually needed them (M2, M3); rule_stats is still "indicative, not
final" — it lands with whatever milestone builds `spork rules stats`,
which hasn't yet.
"""
