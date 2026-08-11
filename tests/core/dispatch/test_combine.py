"""Acceptance tests for combining multi-target dispatch into one decision
(docs/DESIGN.md §9.2).

Covers both built-in Combiners and the integration claim that
DispatchingClassifier needs no changes to the (already-shipped) rule
engine to be usable as its classifier.
"""

from __future__ import annotations

from spork.core.dispatch.combine import (
    DispatchingClassifier,
    HighestConfidenceCombiner,
    PrimaryCombiner,
)
from spork.core.dispatch.dispatcher import Dispatcher

from spork.core.classify.base import ClassificationResult
from spork.core.models import NormalizedMessage
from spork.core.rules.engine import evaluate
from spork.core.rules.schema import Action, Condition, Rule


class _FixedClassifier:
    def __init__(self, category: str, scores: dict[str, float] | None = None) -> None:
        self._result = ClassificationResult(category=category, scores=scores or {})

    def classify(self, message: NormalizedMessage) -> ClassificationResult:
        return self._result


def test_primary_combiner_returns_the_named_targets_result(make_message) -> None:
    """PrimaryCombiner always defers to one named target, ignoring the
    rest — the "others ran but only this one is the decision" case."""
    dispatcher = Dispatcher(
        {
            "production": _FixedClassifier("newsletter"),
            "candidate": _FixedClassifier("urgent"),
        }
    )
    combiner = PrimaryCombiner(primary_name="production")

    combined = combiner.combine(dispatcher.dispatch(make_message()))

    assert combined == ClassificationResult(category="newsletter")


def test_highest_confidence_combiner_picks_the_highest_scoring_result(make_message) -> None:
    """Among successful results, the one with the highest reported
    confidence score wins — a genuine ensemble/voting example."""
    dispatcher = Dispatcher(
        {
            "cautious": _FixedClassifier("newsletter", scores={"newsletter": 0.4}),
            "confident": _FixedClassifier("urgent", scores={"urgent": 0.9}),
        }
    )
    combiner = HighestConfidenceCombiner()

    combined = combiner.combine(dispatcher.dispatch(make_message()))

    assert combined.category == "urgent"


def test_dispatching_classifier_feeds_the_existing_rule_engine_unmodified(make_message) -> None:
    """A DispatchingClassifier satisfies TextClassifier, so it plugs
    straight into rules.engine.evaluate() exactly like a single
    classifier would — no rule-engine changes required for an ensemble.
    """
    dispatcher = Dispatcher(
        {
            "cautious": _FixedClassifier("newsletter", scores={"newsletter": 0.3}),
            "confident": _FixedClassifier("urgent", scores={"urgent": 0.95}),
        }
    )
    ensemble = DispatchingClassifier(dispatcher, HighestConfidenceCombiner())
    rules = [
        Rule(
            id="urgent-escalate",
            when=Condition(local_classifier_category_in=["urgent"]),
            action=Action(type="escalate"),
        )
    ]

    verdict = evaluate(
        make_message(),
        rules,
        default_unmatched_action=Action(type="ignore"),
        classifier=ensemble,
    )

    assert verdict.matched_rule_id == "urgent-escalate"
