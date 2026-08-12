"""daily_call_budget enforcement (docs/DESIGN.md §10.4).

Deliberately decoupled from `StateDB` — a pure function of
`(usage, daily_call_budget)`, the same way `spork.core.llm.confidence`
is decoupled from `Verdict`. A future `BudgetGateSelector` calls
`StateDB.get_llm_usage()` then this function, the same two-step shape
`IdempotencyGateSelector` already uses for `has_processed()`.
"""

from __future__ import annotations

from spork.core.state.db import LLMUsage


def has_budget_remaining(usage: LLMUsage, *, daily_call_budget: int) -> bool:
    """True if another Tier 2 call is allowed today.

    The limit is exclusive: exactly `daily_call_budget` calls already
    made means no budget remains, not "one more allowed."
    """
    return usage.calls < daily_call_budget
