"""Acceptance tests for KeywordClassifier — the dependency-free default
local classifier (docs/DESIGN.md §9.1).

The default `TextClassifier` backend §9.1 has always documented but
never shipped: `tiering.local_classifier` had no working out-of-the-box
value, since nothing anywhere in the codebase ever called
`registry.register()`. This is the correctness half; test_registration.py
covers the self-registration wiring.
"""

from __future__ import annotations

from spork.core.classify.base import ClassificationResult, TextClassifier
from spork.core.classify.keyword import DEFAULT_CATEGORY, KeywordClassifier


def test_keyword_classifier_picks_the_category_whose_keywords_matched(make_message) -> None:
    message = make_message(subject="URGENT: action required", body_text="Please reply asap.")

    result = KeywordClassifier().classify(message)

    assert result.category == "urgent"


def test_keyword_classifier_matching_is_case_insensitive(make_message) -> None:
    message = make_message(subject="Urgent request", body_text="Needs a reply ASAP please.")

    result = KeywordClassifier().classify(message)

    assert result.category == "urgent"


def test_keyword_classifier_falls_back_to_the_default_category_when_nothing_matches(
    make_message,
) -> None:
    message = make_message(subject="Dinner Friday?", body_text="Want to grab dinner Friday?")

    result = KeywordClassifier().classify(message)

    assert result.category == DEFAULT_CATEGORY
    assert all(score == 0.0 for score in result.scores.values())


def test_keyword_classifier_exposes_every_configured_categorys_score(make_message) -> None:
    """scores is an open bag exposing every configured category's
    fraction, not just the winning one — a rule or a future tuning
    pass can key off finer-grained signals (docs/DESIGN.md §9.1)."""
    message = make_message(subject="Newsletter", body_text="Click here to unsubscribe.")

    result = KeywordClassifier().classify(message)

    assert result.category == "newsletter"
    assert set(result.scores) >= {"urgent", "newsletter", "receipt"}
    assert result.scores["newsletter"] > 0.0
    assert result.scores["urgent"] == 0.0


def test_keyword_classifier_accepts_a_custom_category_keyword_mapping(make_message) -> None:
    """Not hardcoded to the shipped default set — a deployment can
    supply its own vocabulary entirely via the constructor."""
    classifier = KeywordClassifier(category_keywords={"invoice": ("invoice", "amount due")})
    message = make_message(subject="Invoice #123", body_text="Amount due: $50.")

    result = classifier.classify(message)

    assert result.category == "invoice"
    assert result.scores == {"invoice": 1.0}


def test_keyword_classifier_structurally_satisfies_textclassifier(make_message) -> None:
    classifier: TextClassifier = KeywordClassifier()

    result = classifier.classify(make_message())

    assert isinstance(result, ClassificationResult)
