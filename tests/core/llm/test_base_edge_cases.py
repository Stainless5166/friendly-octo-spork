"""Failure/edge-case tests for spork.core.llm.base.

Companion to test_base.py's acceptance tests.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from spork.core.llm.base import Verdict


def _verdict_json(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "category": "needs_reply",
        "urgency": "high",
        "confidence": 0.78,
        "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
        "summary": "Client wants to move Thursday's call to Friday 2pm.",
        "reasoning": "Sender asked a direct scheduling question.",
    }
    defaults.update(overrides)
    return defaults


def test_verdict_rejects_a_suggested_action_of_escalate() -> None:
    """A verdict already *is* Tier 2's output — its own
    suggested_action can't be "escalate" (there's nowhere further to
    go); that's a schema-level contradiction, caught here rather than
    reaching ActionExecutor (which would reject it anyway, just later
    and less clearly)."""
    with pytest.raises(ValidationError, match="escalate"):
        Verdict.model_validate(_verdict_json(suggested_action={"type": "escalate"}))


def test_verdict_rejects_confidence_above_one() -> None:
    """confidence is a probability — out of [0, 1] is a malformed
    response, not something to silently clamp."""
    with pytest.raises(ValidationError):
        Verdict.model_validate(_verdict_json(confidence=1.5))


def test_verdict_rejects_confidence_below_zero() -> None:
    with pytest.raises(ValidationError):
        Verdict.model_validate(_verdict_json(confidence=-0.1))


def test_verdict_rejects_an_urgency_outside_the_closed_set() -> None:
    """urgency is a closed Literal (low/medium/high) — an LLM
    inventing a fourth value is a validation failure, not a silent
    pass-through."""
    with pytest.raises(ValidationError):
        Verdict.model_validate(_verdict_json(urgency="critical"))


def test_verdict_rejects_a_malformed_nested_suggested_action() -> None:
    """suggested_action reuses rules.schema.Action wholesale — its own
    validation (extra="forbid", closed `type` set) applies
    transitively, not just Verdict's own top-level fields."""
    with pytest.raises(ValidationError):
        Verdict.model_validate(_verdict_json(suggested_action={"type": "tag", "bogus_field": True}))
