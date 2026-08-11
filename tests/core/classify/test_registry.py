"""Acceptance tests for the local-classifier registry (docs/DESIGN.md §9.1).

Only spork's own registration/lookup behavior is under test here — the
point of this registry is the modularity contract (swap a backend by
name, fail loudly on a bad name), not any particular classifier's
correctness.
"""

from __future__ import annotations

import pytest
from spork.core.classify.base import ClassificationResult, TextClassifier
from spork.core.models import NormalizedMessage

from spork.core.classify import registry


class _StubClassifier:
    """Minimal TextClassifier used only to prove registry plumbing works."""

    def classify(self, message: NormalizedMessage) -> ClassificationResult:
        return ClassificationResult(category="stub")


def test_registry_resolves_registered_classifier_by_name() -> None:
    """A backend registered under a name is returned by get() under that name."""
    registry.register("test-stub-classifier", _StubClassifier)

    resolved: TextClassifier = registry.get("test-stub-classifier")

    assert isinstance(resolved, _StubClassifier)


def test_registry_raises_clear_error_for_unknown_classifier_name() -> None:
    """An unregistered name fails loudly (§9.1's "no implicit fallback" rule)
    instead of silently returning None or some default backend."""
    with pytest.raises(registry.UnknownClassifierError):
        registry.get("this-name-was-never-registered")
