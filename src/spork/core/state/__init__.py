"""Persistent daemon state (docs/DESIGN.md §7.4).

The only state spork keeps across restarts: where it left off (the
push cursor) and what it's already acted on (processed_messages, for
idempotency). Deliberately not a home for anything derived/rebuildable
— audit_log, rule_stats, and llm_usage (also §7.4) land with the
milestones that actually need them (M2, M2, M3 respectively), not here.
"""
