"""Acceptance tests for classifier fan-out (docs/DESIGN.md §9.2).

Dispatcher is exercised against plain stub TextClassifier objects —
never a real classifier backend or third-party library — so these test
only spork's own fan-out/failure-isolation behavior.
"""

from __future__ import annotations

from spork.core.classify.base import ClassificationResult
from spork.core.dispatch.dispatcher import Dispatcher
from spork.core.models import NormalizedMessage


class _FixedClassifier:
    """Always returns the same ClassificationResult, regardless of message."""

    def __init__(self, category: str) -> None:
        self._category = category

    def classify(self, message: NormalizedMessage) -> ClassificationResult:
        return ClassificationResult(category=self._category)


class _FailingClassifier:
    """Simulates a broken/experimental classifier backend."""

    def classify(self, message: NormalizedMessage) -> ClassificationResult:
        raise RuntimeError("simulated classifier failure")


def test_dispatch_runs_all_targets_and_collects_results(make_message) -> None:
    """dispatch() returns every target's result, keyed by target name."""
    dispatcher = Dispatcher(
        {
            "production": _FixedClassifier("newsletter"),
            "candidate": _FixedClassifier("urgent"),
        }
    )

    results = dispatcher.dispatch(make_message())

    assert results["production"] == ClassificationResult(category="newsletter")
    assert results["candidate"] == ClassificationResult(category="urgent")


def test_dispatch_with_a_single_target(make_message) -> None:
    """Dispatching to one target is just the N=1 case, not a special path."""
    dispatcher = Dispatcher({"only": _FixedClassifier("spam")})

    results = dispatcher.dispatch(make_message())

    assert results == {"only": ClassificationResult(category="spam")}


def test_dispatch_isolates_a_failing_target_from_the_others(make_message) -> None:
    """A target that raises doesn't abort the dispatch or the other targets —
    its exception is captured as its own result entry instead."""
    dispatcher = Dispatcher(
        {
            "production": _FixedClassifier("newsletter"),
            "broken_candidate": _FailingClassifier(),
        }
    )

    results = dispatcher.dispatch(make_message())

    assert results["production"] == ClassificationResult(category="newsletter")
    assert isinstance(results["broken_candidate"], RuntimeError)
