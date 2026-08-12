"""Acceptance tests for spork.core.llm.budget (docs/DESIGN.md §10.4).

has_budget_remaining() is pure: a function of (usage, daily_call_budget),
decoupled from StateDB the same way confidence_band() is decoupled
from Verdict.
"""

from __future__ import annotations

from spork.core.llm.budget import has_budget_remaining
from spork.core.state.db import LLMUsage


def test_budget_remaining_when_calls_are_below_the_limit() -> None:
    """Fewer calls made today than the configured budget: more calls
    are allowed."""
    usage = LLMUsage(date="2026-08-12", calls=5, tokens_in=0, tokens_out=0)

    assert has_budget_remaining(usage, daily_call_budget=200) is True


def test_no_budget_remaining_once_the_limit_is_reached() -> None:
    """Exactly at the configured budget: no more calls today — the
    limit is exclusive, not "one more allowed once you hit it"."""
    usage = LLMUsage(date="2026-08-12", calls=200, tokens_in=0, tokens_out=0)

    assert has_budget_remaining(usage, daily_call_budget=200) is False


def test_no_budget_remaining_once_the_limit_is_exceeded() -> None:
    """More calls recorded than the budget allows (e.g. budget was
    lowered mid-day): still no budget remaining, not a negative-count
    error."""
    usage = LLMUsage(date="2026-08-12", calls=250, tokens_in=0, tokens_out=0)

    assert has_budget_remaining(usage, daily_call_budget=200) is False


def test_budget_remaining_on_a_never_called_day() -> None:
    """A day with zero recorded calls (StateDB.get_llm_usage()'s
    zeroed default) always has budget remaining, for any positive
    budget."""
    usage = LLMUsage(date="2026-08-12", calls=0, tokens_in=0, tokens_out=0)

    assert has_budget_remaining(usage, daily_call_budget=1) is True
