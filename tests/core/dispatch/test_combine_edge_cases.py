"""Failure/edge-case tests for combining multi-target dispatch results.

Companion to test_combine.py's acceptance tests — covers the ways a
Combiner can fail to produce a decision, and confirms tie-breaking is
deterministic rather than incidental.
"""

from __future__ import annotations

import pytest

from spork.core.classify.base import ClassificationResult
from spork.core.dispatch.combine import (
    CombineError,
    DispatchingClassifier,
    HighestConfidenceCombiner,
    PrimaryCombiner,
)
from spork.core.dispatch.dispatcher import Dispatcher
from spork.core.models import NormalizedMessage


def test_primary_combiner_raises_when_named_target_missing() -> None:
    """A typo'd/misconfigured primary_name fails loudly rather than
    silently returning some other target's result."""
    combiner = PrimaryCombiner(primary_name="does-not-exist")

    with pytest.raises(CombineError, match="was not in the dispatch"):
        combiner.combine({"production": ClassificationResult(category="newsletter")})


def test_primary_combiner_raises_when_named_target_failed() -> None:
    """If the primary target itself raised during dispatch, that's not
    silently swallowed by falling back to another target's result."""
    combiner = PrimaryCombiner(primary_name="production")

    with pytest.raises(CombineError, match="failed to classify"):
        combiner.combine({"production": RuntimeError("simulated failure")})


def test_highest_confidence_combiner_raises_when_all_targets_failed() -> None:
    """No successful result anywhere means no decision can be produced —
    this must never resolve to some default/empty ClassificationResult."""
    combiner = HighestConfidenceCombiner()

    with pytest.raises(CombineError) as exc_info:
        combiner.combine(
            {
                "a": RuntimeError("failure a"),
                "b": RuntimeError("failure b"),
            }
        )

    # Exact equality, not a substring match — a substring alone can't
    # distinguish the real message from one wrapped in extra characters
    # that still contain the substring (a mutation-testing target).
    assert str(exc_info.value) == "no target produced a successful classification result"


def test_highest_confidence_combiner_treats_no_scores_as_exactly_zero_confidence() -> None:
    """A target reporting no scores at all is confidence 0.0 — not
    disqualified, not auto-preferred (combine.py's own docstring: "not
    preferred by default") — literally 0.0, so it beats a real negative
    score and loses to a real positive one. HighestConfidenceCombiner's
    `max(..., default=0.0)` is only exercised on the empty-scores path,
    which a randomized/property test only reaches sometimes; pinned
    here deterministically instead."""
    combiner = HighestConfidenceCombiner()

    beats_negative = combiner.combine(
        {
            "quiet": ClassificationResult(category="quiet", scores={}),
            "negative": ClassificationResult(category="negative", scores={"x": -0.5}),
        }
    )
    assert beats_negative.category == "quiet"

    loses_to_positive = combiner.combine(
        {
            "quiet": ClassificationResult(category="quiet", scores={}),
            "positive": ClassificationResult(category="positive", scores={"x": 0.5}),
        }
    )
    assert loses_to_positive.category == "positive"


def test_highest_confidence_combiner_breaks_ties_by_target_order() -> None:
    """Two targets reporting the same top confidence resolve
    deterministically to whichever appears first in the results
    mapping, not to whichever happens to hash first."""
    combiner = HighestConfidenceCombiner()
    results = {
        "first": ClassificationResult(category="a", scores={"a": 0.5}),
        "second": ClassificationResult(category="b", scores={"b": 0.5}),
    }

    combined = combiner.combine(results)

    assert combined.category == "a"


def test_dispatching_classifier_forwards_the_actual_message_to_dispatch(make_message) -> None:
    """classify(message) must hand *that* message to the dispatcher —
    not some other value — since every target's classify() depends on
    the real message content to produce a meaningful result."""

    class _RecordingClassifier:
        def __init__(self) -> None:
            self.messages_seen: list[NormalizedMessage] = []

        def classify(self, message: NormalizedMessage) -> ClassificationResult:
            self.messages_seen.append(message)
            return ClassificationResult(category="newsletter")

    target = _RecordingClassifier()
    dispatcher = Dispatcher({"only": target})
    classifier = DispatchingClassifier(dispatcher, PrimaryCombiner(primary_name="only"))
    message = make_message()

    classifier.classify(message)

    assert target.messages_seen == [message]
