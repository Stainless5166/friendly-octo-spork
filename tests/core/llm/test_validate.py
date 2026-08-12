"""Acceptance tests for spork.core.llm.validate (docs/DESIGN.md §10.2).

validate_verdict() is pure: no I/O, no Provider/JMAP dependency —
allowed_categories/allowed_mailboxes are passed in already resolved.
"""

from __future__ import annotations

import pytest

from spork.core.llm.base import Verdict
from spork.core.llm.validate import VerdictValidationError, validate_verdict


def _verdict(**overrides: object) -> Verdict:
    payload: dict[str, object] = {
        "category": "needs_reply",
        "urgency": "high",
        "confidence": 0.78,
        "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
        "summary": "Client wants to move Thursday's call to Friday 2pm.",
        "reasoning": "Sender asked a direct scheduling question.",
    }
    payload.update(overrides)
    return Verdict.model_validate(payload)


def test_validate_verdict_returns_the_verdict_unchanged_on_success() -> None:
    """A verdict whose category and mailbox are both in the configured
    sets passes through untouched — validation never coerces."""
    verdict = _verdict()

    result = validate_verdict(
        verdict,
        allowed_categories=["needs_reply", "fyi"],
        allowed_mailboxes=["Inbox", "Needs-Reply"],
    )

    assert result is verdict


def test_validate_verdict_rejects_a_category_outside_the_configured_set() -> None:
    """A category this deployment never configured (a model
    hallucination, or a config that dropped one) is a validation
    failure naming the bad value."""
    verdict = _verdict(category="urgent_escalation")

    with pytest.raises(VerdictValidationError, match="urgent_escalation"):
        validate_verdict(
            verdict,
            allowed_categories=["needs_reply", "fyi"],
            allowed_mailboxes=["Inbox", "Needs-Reply"],
        )


def test_validate_verdict_rejects_a_mailbox_outside_the_configured_set() -> None:
    """suggested_action.mailbox naming a mailbox this deployment never
    configured is a validation failure naming the bad value."""
    verdict = _verdict(suggested_action={"type": "move", "mailbox": "Nonexistent"})

    with pytest.raises(VerdictValidationError, match="Nonexistent"):
        validate_verdict(
            verdict,
            allowed_categories=["needs_reply"],
            allowed_mailboxes=["Inbox", "Needs-Reply"],
        )


def test_validate_verdict_skips_the_mailbox_check_when_mailbox_is_none() -> None:
    """suggested_action.mailbox is meaningful only for move/tag
    (rules.schema.Action's own docstring) — an ignore verdict with no
    mailbox set passes even against an empty allowed_mailboxes list."""
    verdict = _verdict(category="fyi", suggested_action={"type": "ignore"})

    result = validate_verdict(verdict, allowed_categories=["fyi"], allowed_mailboxes=[])

    assert result is verdict
