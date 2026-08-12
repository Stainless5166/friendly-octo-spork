"""Failure/edge-case tests for spork.core.llm.validate.

Companion to test_validate.py's acceptance tests.
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


def test_validate_verdict_reports_the_category_error_first_when_both_are_invalid() -> None:
    """When both category and mailbox are out of set, the category
    check runs first — documents the actual precedence (not load-
    bearing behavior, but a caller reading only the first exception
    shouldn't be surprised which one it is)."""
    verdict = _verdict(
        category="bogus_category",
        suggested_action={"type": "move", "mailbox": "Bogus-Mailbox"},
    )

    with pytest.raises(VerdictValidationError, match="bogus_category"):
        validate_verdict(verdict, allowed_categories=["needs_reply"], allowed_mailboxes=["Inbox"])


def test_validate_verdict_category_check_is_case_sensitive() -> None:
    """A configured "Needs_Reply" doesn't match a verdict's
    "needs_reply" — category/mailbox names are exact strings from
    config.toml/JMAP, not normalized or fuzzy-matched anywhere."""
    verdict = _verdict(category="needs_reply")

    with pytest.raises(VerdictValidationError):
        validate_verdict(verdict, allowed_categories=["Needs_Reply"], allowed_mailboxes=["Inbox"])


def test_validate_verdict_does_not_itself_require_a_mailbox_for_move_or_tag() -> None:
    """BUG/GAP FOUND WHILE TESTING: rules.schema.Action.mailbox is
    optional at the pydantic level even for type="move"/"tag" (nothing
    in Verdict's or Action's own schema requires it) — so a verdict
    like {"type": "move"} with no mailbox at all passes both Verdict
    parsing and validate_verdict() here (there's no mailbox value to
    check against allowed_mailboxes, so the check is trivially
    skipped). This is NOT a silent hole in practice: ActionExecutor
    (spork.core.actions.executor) independently rejects a move/tag
    action with mailbox=None via ActionExecutionError before it's ever
    applied — the same invariant Tier 1 rules already rely on, reused
    here rather than duplicated. Documented as a test, not "fixed" in
    validate_verdict, so a future reader doesn't assume this function
    is supposed to catch it and doesn't accidentally leave *both*
    checks silently absent if ActionExecutor's ever refactored."""
    verdict = _verdict(category="needs_reply", suggested_action={"type": "move"})

    result = validate_verdict(verdict, allowed_categories=["needs_reply"], allowed_mailboxes=[])

    assert result.suggested_action.mailbox is None
