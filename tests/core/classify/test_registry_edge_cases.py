"""Failure/edge-case tests for the local-classifier registry.

Companion to test_registry.py's acceptance tests — covers duplicate
registration and the "factories aren't constructed until selected"
guarantee from docs/DESIGN.md §9.1.
"""

from __future__ import annotations

import pytest

from spork.core.classify import registry
from spork.core.classify.base import ClassificationResult
from spork.core.models import NormalizedMessage


class _StubClassifier:
    """Minimal TextClassifier used only to prove registry plumbing works."""

    def classify(self, message: NormalizedMessage) -> ClassificationResult:
        return ClassificationResult(category="stub")


def test_registering_a_duplicate_name_raises() -> None:
    """Re-registering an already-used name is rejected, not silently
    overwritten — a collision here is almost always a bug (duplicate
    import, copy-pasted registration), not an intentional override."""
    registry.register("dup-name", _StubClassifier)

    with pytest.raises(ValueError):
        registry.register("dup-name", _StubClassifier)


def test_unselected_backends_are_never_constructed() -> None:
    """A registered-but-unrequested backend's factory is never called.

    Backends are stored as factories precisely so an expensive
    construction (e.g. loading a model file) only happens for the one
    backend actually selected (docs/DESIGN.md §9.1).
    """
    constructed: list[str] = []

    class TrackedA:
        def __init__(self) -> None:
            constructed.append("a")

        def classify(self, message: NormalizedMessage) -> ClassificationResult:
            return ClassificationResult(category="a")

    class TrackedB:
        def __init__(self) -> None:
            constructed.append("b")

        def classify(self, message: NormalizedMessage) -> ClassificationResult:
            return ClassificationResult(category="b")

    registry.register("tracked-a", TrackedA)
    registry.register("tracked-b", TrackedB)

    registry.get("tracked-b")

    assert constructed == ["b"]
