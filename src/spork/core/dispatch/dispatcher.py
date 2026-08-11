"""Classifier fan-out (docs/DESIGN.md §9.2).

The whole point of dispatching to multiple targets is to let a
half-finished or experimental classifier run alongside a production
one — so a target raising must never take the others down with it.
That failure-isolation requirement is this module's only real job;
everything else is bookkeeping.
"""

from __future__ import annotations

from collections.abc import Mapping

from spork.core.classify.base import ClassificationResult, TextClassifier
from spork.core.models import NormalizedMessage

# One target's outcome from a dispatch: its result, or the exception it
# raised. Using the exception itself as the value (rather than a
# wrapper type) keeps this a plain, inspectable dict — `isinstance(v,
# Exception)` is enough to tell the two cases apart.
DispatchResult = dict[str, "ClassificationResult | Exception"]


class Dispatcher:
    """Runs every configured target's classify() against one message.

    Takes already-constructed `TextClassifier` instances (not names to
    resolve via `spork.core.classify.registry`) — resolving names to
    backends is config-wiring, a daemon-startup concern kept separate
    from this class so it stays trivially testable with stub targets.
    """

    def __init__(self, targets: Mapping[str, TextClassifier]) -> None:
        self._targets = dict(targets)

    def dispatch(self, message: NormalizedMessage) -> DispatchResult:
        """Classify `message` with every target; one is just the N=1 case.

        A target whose classify() raises has that exception captured
        as its result entry rather than propagated — see module
        docstring for why. Callers that need "did everything succeed"
        can check `isinstance(value, Exception)` per entry.
        """
        results: DispatchResult = {}
        for name, target in self._targets.items():
            try:
                results[name] = target.classify(message)
            except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
                results[name] = exc
        return results
