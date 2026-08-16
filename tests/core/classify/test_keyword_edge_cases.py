"""Failure/edge-case tests for KeywordClassifier.

Companion to test_keyword.py's acceptance tests.
"""

from __future__ import annotations

from spork.core.classify.keyword import KeywordClassifier


def test_keyword_classifier_scores_a_category_with_an_empty_keyword_list_as_zero(
    make_message,
) -> None:
    """A misconfigured category (an empty keyword tuple) never crashes
    with a divide-by-zero — it just can never win, scored 0.0 like any
    other unmatched category."""
    classifier = KeywordClassifier(category_keywords={"empty": (), "urgent": ("urgent",)})
    message = make_message(subject="Urgent!", body_text="Please respond.")

    result = classifier.classify(message)

    assert result.scores["empty"] == 0.0
    assert result.category == "urgent"
