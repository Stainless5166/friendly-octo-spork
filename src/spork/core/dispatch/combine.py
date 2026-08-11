"""Reducing a multi-target dispatch to the one decision a rule acts on.

Complements `dispatcher.py`: that module answers "what did every
target say", this module answers "so which one wins" — kept as a
separate, swappable step so a bespoke combining strategy (majority
vote, "escalate if any target says urgent") never needs to touch
`Dispatcher` itself.
"""

from __future__ import annotations

from typing import Protocol

from spork.core.classify.base import ClassificationResult
from spork.core.dispatch.dispatcher import Dispatcher, DispatchResult
from spork.core.models import NormalizedMessage


class CombineError(ValueError):
    """Raised when a Combiner cannot produce a single result.

    Covers both "the target this Combiner needed wasn't dispatched to"
    and "every target failed" — a distinct type so callers can catch
    precisely this rather than a bare ValueError from elsewhere.
    """


class Combiner(Protocol):
    """Reduces one dispatch's per-target results to a single decision."""

    def combine(self, results: DispatchResult) -> ClassificationResult: ...


class PrimaryCombiner:
    """Always defers to one named target; the rest are informational.

    This is "shadow mode" expressed as a Combiner: every configured
    target still runs (useful for logging/comparison via the raw
    dispatch results), but only `primary_name`'s opinion is ever the
    decision — a candidate classifier can run for weeks without being
    able to affect behavior until someone deliberately promotes it.
    """

    def __init__(self, primary_name: str) -> None:
        self._primary_name = primary_name

    def combine(self, results: DispatchResult) -> ClassificationResult:
        try:
            outcome = results[self._primary_name]
        except KeyError as exc:
            raise CombineError(
                f"primary target {self._primary_name!r} was not in the dispatch "
                f"results; available: {sorted(results)}"
            ) from exc
        if isinstance(outcome, Exception):
            raise CombineError(
                f"primary target {self._primary_name!r} failed to classify"
            ) from outcome
        return outcome


class HighestConfidenceCombiner:
    """Picks whichever successful target reported the highest confidence.

    A genuine ensemble strategy (as opposed to PrimaryCombiner's
    "ignore everyone but one"): every target's opinion can win, decided
    per-message by how confident each one claims to be. A target's
    confidence is the max of its own `scores` values — if it reported
    nothing, it's treated as 0.0 confidence, not preferred by default.
    """

    def combine(self, results: DispatchResult) -> ClassificationResult:
        successes = {
            name: outcome for name, outcome in results.items() if not isinstance(outcome, Exception)
        }
        if not successes:
            raise CombineError("no target produced a successful classification result")

        def confidence(result: ClassificationResult) -> float:
            return max(result.scores.values(), default=0.0)

        # dict iteration (and therefore max()'s tie-break) follows
        # insertion order, i.e. the targets mapping's order — a tie is
        # resolved deterministically, not by hash order.
        best_name = max(successes, key=lambda name: confidence(successes[name]))
        return successes[best_name]


class DispatchingClassifier:
    """A TextClassifier whose classify() dispatches to N targets and combines them.

    The integration point that makes §9.2 cheap: because this
    satisfies the same `TextClassifier` protocol as any single
    backend, `spork.core.rules.engine.evaluate()` can consume an
    ensemble of classifiers exactly as it consumes one, with no
    changes to the rule engine at all.
    """

    def __init__(self, dispatcher: Dispatcher, combiner: Combiner) -> None:
        self._dispatcher = dispatcher
        self._combiner = combiner

    def classify(self, message: NormalizedMessage) -> ClassificationResult:
        return self._combiner.combine(self._dispatcher.dispatch(message))
