"""Property-based tests for combining multi-target dispatch (docs/DESIGN.md §16.1).

Companion to test_combine.py/test_combine_edge_cases.py's example-based
tests — these state invariants over Hypothesis-generated DispatchResults
rather than a couple of hand-picked target maps.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from spork.core.classify.base import ClassificationResult
from spork.core.dispatch.combine import (
    CombineError,
    DispatchingClassifier,
    HighestConfidenceCombiner,
    PrimaryCombiner,
)
from spork.core.dispatch.dispatcher import Dispatcher, DispatchResult
from spork.core.models import NormalizedMessage

_CONFIDENCE = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)

# DispatchingClassifier.classify() never reads message content itself
# (it hands the message straight to the dispatcher) — one fixed message
# is enough, and avoids Hypothesis's function-scoped fixture health
# check for reusing a pytest fixture across @given's generated examples.
_MESSAGE = NormalizedMessage(
    message_id="msg-1",
    thread_id="thread-1",
    from_address="someone@example.com",
    from_domain="example.com",
    subject="Test subject",
    body_text="Test body.",
)


def _confidence(result: ClassificationResult) -> float:
    """Mirrors HighestConfidenceCombiner's own definition (combine.py) —
    the oracle these properties check the real implementation against."""
    return max(result.scores.values(), default=0.0)


@st.composite
def _classification_results(draw: st.DrawFn) -> ClassificationResult:
    category = draw(st.text(max_size=15))
    scores = draw(st.dictionaries(st.text(max_size=8), _CONFIDENCE, max_size=4))
    return ClassificationResult(category=category, scores=scores)


@st.composite
def _dispatch_results(draw: st.DrawFn) -> DispatchResult:
    """An arbitrary DispatchResult: a name -> (success | failure) map,
    same shape Dispatcher.dispatch() produces (dispatcher.py)."""
    outcomes = st.one_of(
        _classification_results(),
        st.builds(RuntimeError, st.text(max_size=20)),
    )
    return draw(st.dictionaries(st.text(min_size=1, max_size=8), outcomes, max_size=6))


class _FixedClassifier:
    """A TextClassifier stub that always returns one pre-built result."""

    def __init__(self, result: ClassificationResult) -> None:
        self._result = result

    def classify(self, message: NormalizedMessage) -> ClassificationResult:
        return self._result


@given(results=_dispatch_results(), primary_name=st.text(min_size=1, max_size=8))
def test_primary_combiner_returns_exactly_the_named_targets_success_or_raises(
    results: DispatchResult, primary_name: str
) -> None:
    """PrimaryCombiner's decision is entirely a function of one lookup:
    the named target's outcome, if it succeeded — never any other
    target's result, whatever else is in the dispatch map."""
    combiner = PrimaryCombiner(primary_name=primary_name)
    outcome = results.get(primary_name)

    if isinstance(outcome, ClassificationResult):
        combined = combiner.combine(results)
        assert combined == outcome
    else:
        # missing key (outcome is None) and a failed target (outcome is
        # an Exception) are both rejection cases — not distinguished
        # from the caller's side.
        with pytest.raises(CombineError):
            combiner.combine(results)


@given(results=_dispatch_results())
def test_highest_confidence_combiner_picks_the_max_confidence_success_or_raises(
    results: DispatchResult,
) -> None:
    """Whatever mix of successes/failures Hypothesis generates, the
    combiner either raises (no successes at all) or returns a result
    whose confidence ties the best confidence among the successes — it
    can never under- or over-shoot the true maximum."""
    combiner = HighestConfidenceCombiner()
    successes = [r for r in results.values() if isinstance(r, ClassificationResult)]

    if not successes:
        with pytest.raises(CombineError):
            combiner.combine(results)
        return

    combined = combiner.combine(results)

    assert combined in successes
    assert _confidence(combined) == max(_confidence(r) for r in successes)


@given(
    tie_confidence=_CONFIDENCE,
    extra_names=st.lists(st.text(min_size=1, max_size=6), max_size=3, unique=True),
)
def test_highest_confidence_tie_break_favors_earlier_insertion_order(
    tie_confidence: float, extra_names: list[str]
) -> None:
    """Two targets tied for the top confidence resolve to whichever
    appears first in the results mapping, for any generated tie value —
    generalizes the fixed-0.5 example in test_combine_edge_cases.py."""
    combiner = HighestConfidenceCombiner()
    results: DispatchResult = {
        "first": ClassificationResult(category="first", scores={"s": tie_confidence}),
        "second": ClassificationResult(category="second", scores={"s": tie_confidence}),
    }
    # Any extra targets must report strictly lower confidence, so they
    # can't win and mask what this property is actually checking.
    for i, name in enumerate(extra_names):
        if name in results:
            continue
        results[name] = ClassificationResult(category=name, scores={"s": tie_confidence - i - 1})

    combined = combiner.combine(results)

    assert combined.category == "first"


@given(
    successes=st.dictionaries(
        st.text(min_size=1, max_size=6), _classification_results(), min_size=1, max_size=5
    )
)
def test_dispatching_classifier_matches_manual_dispatch_then_combine(
    successes: dict[str, ClassificationResult],
) -> None:
    """DispatchingClassifier.classify() is exactly dispatch-then-combine —
    no logic of its own that could drift from either piece it wires
    together (§9.2's whole point: the rule engine needs no changes to
    consume this as a plain TextClassifier)."""
    targets = {name: _FixedClassifier(result) for name, result in successes.items()}
    dispatcher = Dispatcher(targets)
    combiner = HighestConfidenceCombiner()
    classifier = DispatchingClassifier(dispatcher, combiner)

    assert classifier.classify(_MESSAGE) == combiner.combine(dispatcher.dispatch(_MESSAGE))
