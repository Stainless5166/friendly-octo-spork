"""Failure/edge-case tests for the Tier 1 rule engine (docs/DESIGN.md §9).

Companion to test_engine.py's acceptance tests — covers empty input,
the "no fields set" condition footgun, the classifier-required error
path, and classifier memoization, none of which the happy-path
acceptance tests exercise.
"""

from __future__ import annotations

from typing import Any

import pytest

from spork.core.classify.base import ClassificationResult
from spork.core.models import NormalizedMessage
from spork.core.rules.engine import evaluate
from spork.core.rules.schema import Action, Condition, Rule


def test_empty_rule_list_returns_default_policy(make_message: Any) -> None:
    """No rules at all behaves the same as "no rule matched"."""
    message = make_message()

    verdict = evaluate(message, [], default_unmatched_action=Action(type="ignore"))

    assert verdict.matched_rule_id is None
    assert verdict.action == Action(type="ignore")


def test_condition_with_no_fields_set_never_matches(make_message: Any) -> None:
    """An all-default Condition matches nothing, not everything.

    Guards against a hand-edited rules.toml entry that forgot to set
    any `when` field silently becoming an accidental catch-all.
    """
    message = make_message()
    rules = [
        Rule(id="empty-condition", when=Condition(), action=Action(type="ignore")),
        Rule(
            id="fallback",
            when=Condition(always=True),
            action=Action(type="tag", mailbox="X"),
        ),
    ]

    verdict = evaluate(message, rules, default_unmatched_action=Action(type="escalate"))

    assert verdict.matched_rule_id == "fallback"


def test_classifier_condition_without_configured_classifier_raises(make_message: Any) -> None:
    """A rule needing classifier output with none configured fails loudly.

    Per docs/DESIGN.md §9.1: a misconfiguration here must never look
    like "the condition just didn't match".
    """
    message = make_message()
    rules = [
        Rule(
            id="needs-classifier",
            when=Condition(local_classifier_category_in=["urgent"]),
            action=Action(type="escalate"),
        )
    ]

    with pytest.raises(RuntimeError):
        evaluate(message, rules, default_unmatched_action=Action(type="ignore"))


def test_classifier_is_invoked_at_most_once_per_evaluation(make_message: Any) -> None:
    """Multiple classifier-backed conditions checked in one evaluate() call
    only classify the message once (memoized), not once per rule checked."""

    class CountingClassifier:
        def __init__(self) -> None:
            self.calls = 0

        def classify(self, message: NormalizedMessage) -> ClassificationResult:
            self.calls += 1
            return ClassificationResult(category="newsletter")

    classifier = CountingClassifier()
    message = make_message()
    rules = [
        Rule(
            id="not-urgent",
            when=Condition(local_classifier_category_in=["urgent"]),
            action=Action(type="ignore"),
        ),
        Rule(
            id="not-spam",
            when=Condition(local_classifier_category_in=["spam"]),
            action=Action(type="ignore"),
        ),
        Rule(
            id="is-newsletter",
            when=Condition(local_classifier_category_in=["newsletter"]),
            action=Action(type="tag", mailbox="Reading"),
        ),
    ]

    verdict = evaluate(
        message,
        rules,
        default_unmatched_action=Action(type="escalate"),
        classifier=classifier,
    )

    assert verdict.matched_rule_id == "is-newsletter"
    assert classifier.calls == 1
