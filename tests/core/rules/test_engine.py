"""Acceptance tests for the Tier 1 rule engine (docs/DESIGN.md §9).

These exercise spork's own evaluation semantics only — first-match-wins,
disabled-rule skipping, the unmatched-message fallback, and the
classifier-backed condition that demonstrates the §9.1 modularity
contract. None of this tests pydantic, or any other third-party
library's own correctness.
"""

from __future__ import annotations

from typing import Any

from spork.core.classify.base import ClassificationResult, TextClassifier
from spork.core.models import NormalizedMessage
from spork.core.rules.engine import evaluate
from spork.core.rules.schema import Action, Condition, Rule


def test_first_matching_enabled_rule_wins(make_message: Any) -> None:
    """When two enabled rules both match, the earlier rule's action wins."""
    message = make_message(from_domain="newsletter.example.com")
    rules = [
        Rule(
            id="catch-newsletter",
            when=Condition(from_domain_in=["newsletter.example.com"]),
            action=Action(type="move", mailbox="Reading"),
        ),
        Rule(
            id="catch-everything",
            when=Condition(always=True),
            action=Action(type="tag", mailbox="Inbox"),
        ),
    ]

    verdict = evaluate(message, rules, default_unmatched_action=Action(type="escalate"))

    assert verdict.matched_rule_id == "catch-newsletter"
    assert verdict.action == Action(type="move", mailbox="Reading")


def test_disabled_rule_is_skipped_even_if_condition_matches(make_message: Any) -> None:
    """A disabled rule never fires, even when it would otherwise match first."""
    message = make_message(from_domain="newsletter.example.com")
    rules = [
        Rule(
            id="disabled-newsletter-rule",
            when=Condition(from_domain_in=["newsletter.example.com"]),
            action=Action(type="move", mailbox="Reading"),
            enabled=False,
        ),
        Rule(
            id="fallback",
            when=Condition(always=True),
            action=Action(type="tag", mailbox="Inbox"),
        ),
    ]

    verdict = evaluate(message, rules, default_unmatched_action=Action(type="escalate"))

    assert verdict.matched_rule_id == "fallback"


def test_unmatched_message_falls_back_to_default_policy(make_message: Any) -> None:
    """A message matching no enabled rule gets the configured default-unmatched action."""
    message = make_message(from_domain="unrelated.example.com")
    rules = [
        Rule(
            id="only-rule",
            when=Condition(from_domain_in=["newsletter.example.com"]),
            action=Action(type="move", mailbox="Reading"),
        )
    ]

    verdict = evaluate(message, rules, default_unmatched_action=Action(type="escalate"))

    assert verdict.matched_rule_id is None
    assert verdict.action == Action(type="escalate")


def test_from_domain_in_condition_matches_sender_domain(make_message: Any) -> None:
    """from_domain_in matches the message's sender domain, and only that domain."""
    matching = make_message(from_domain="example.com")
    non_matching = make_message(from_domain="notexample.com")
    rules = [
        Rule(
            id="domain-rule",
            when=Condition(from_domain_in=["example.com"]),
            action=Action(type="tag", mailbox="Known"),
        )
    ]

    matched = evaluate(matching, rules, default_unmatched_action=Action(type="escalate"))
    unmatched = evaluate(non_matching, rules, default_unmatched_action=Action(type="escalate"))

    assert matched.matched_rule_id == "domain-rule"
    assert unmatched.matched_rule_id is None


def test_local_classifier_category_condition_consults_configured_classifier(
    make_message: Any,
) -> None:
    """local_classifier_category_in defers to whatever TextClassifier is passed in.

    Exercises the modularity contract from docs/DESIGN.md §9.1: the rule
    engine must not hardcode a classification technique — it only needs
    something satisfying the TextClassifier protocol.
    """

    class StubUrgentClassifier:
        def classify(self, message: NormalizedMessage) -> ClassificationResult:
            return ClassificationResult(category="urgent", scores={"urgent": 0.9})

    classifier: TextClassifier = StubUrgentClassifier()
    message = make_message(subject="drop everything")
    rules = [
        Rule(
            id="urgent-escalate",
            when=Condition(local_classifier_category_in=["urgent"]),
            action=Action(type="escalate", reason="local_classifier_urgent"),
        )
    ]

    verdict = evaluate(
        message,
        rules,
        default_unmatched_action=Action(type="ignore"),
        classifier=classifier,
    )

    assert verdict.matched_rule_id == "urgent-escalate"
    assert verdict.action.reason == "local_classifier_urgent"
