"""Failure/edge-case tests for combining multi-target dispatch results.

Companion to test_combine.py's acceptance tests — covers the ways a
Combiner can fail to produce a decision, and confirms tie-breaking is
deterministic rather than incidental.
"""

from __future__ import annotations

import pytest

from spork.core.classify.base import ClassificationResult
from spork.core.dispatch.combine import CombineError, HighestConfidenceCombiner, PrimaryCombiner


def test_primary_combiner_raises_when_named_target_missing() -> None:
    """A typo'd/misconfigured primary_name fails loudly rather than
    silently returning some other target's result."""
    combiner = PrimaryCombiner(primary_name="does-not-exist")

    with pytest.raises(CombineError):
        combiner.combine({"production": ClassificationResult(category="newsletter")})


def test_primary_combiner_raises_when_named_target_failed() -> None:
    """If the primary target itself raised during dispatch, that's not
    silently swallowed by falling back to another target's result."""
    combiner = PrimaryCombiner(primary_name="production")

    with pytest.raises(CombineError):
        combiner.combine({"production": RuntimeError("simulated failure")})


def test_highest_confidence_combiner_raises_when_all_targets_failed() -> None:
    """No successful result anywhere means no decision can be produced —
    this must never resolve to some default/empty ClassificationResult."""
    combiner = HighestConfidenceCombiner()

    with pytest.raises(CombineError):
        combiner.combine(
            {
                "a": RuntimeError("failure a"),
                "b": RuntimeError("failure b"),
            }
        )


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
