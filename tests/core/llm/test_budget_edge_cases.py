"""Failure/edge-case tests for spork.core.llm.budget.

Companion to test_budget.py's acceptance tests.
"""

from __future__ import annotations

from spork.core.llm.budget import has_budget_remaining
from spork.core.state.db import LLMUsage


def test_a_zero_daily_call_budget_always_denies() -> None:
    """daily_call_budget=0 (an operator explicitly disabling Tier 2)
    denies even before any call has been made today — 0 calls is not
    less than a 0 budget."""
    usage = LLMUsage(date="2026-08-12", calls=0, tokens_in=0, tokens_out=0)

    assert has_budget_remaining(usage, daily_call_budget=0) is False


def test_a_negative_daily_call_budget_always_denies() -> None:
    """Not a config invariant this function rejects (unlike
    confidence.py's threshold ordering) — a negative daily_call_budget
    is nonsensical but not ambiguous: every non-negative call count is
    "over budget" against it, so it behaves exactly like a very
    aggressive 0. Documented rather than guarded against, since there's
    no wrong band to fall into the way swapped confidence thresholds
    would produce."""
    usage = LLMUsage(date="2026-08-12", calls=0, tokens_in=0, tokens_out=0)

    assert has_budget_remaining(usage, daily_call_budget=-5) is False
