"""Failure/edge-case tests for the dynamic Alerter loader.

Companion to test_loader.py's acceptance tests. Mirrors
tests/core/providers/test_loader_edge_cases.py /
tests/core/llm/test_loader_edge_cases.py.
"""

from __future__ import annotations

import pytest

from spork.core.alerts.loader import AlerterLoadError, load_alerter


class _FixtureAlerter:
    def __init__(self, label: str = "default") -> None:
        self.label = label

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: str = "normal"
    ) -> None:  # pragma: no cover - never actually called
        raise NotImplementedError


def test_load_alerter_raises_for_unimportable_module() -> None:
    """A spec naming a module that doesn't exist fails loudly rather
    than a raw ImportError leaking through unwrapped."""
    with pytest.raises(AlerterLoadError):
        load_alerter("this.module.does.not.exist:Whatever")


def test_load_alerter_raises_for_missing_class_attribute() -> None:
    """A spec naming a real module but a class that isn't defined
    there fails loudly rather than a raw AttributeError leaking
    through unwrapped."""
    with pytest.raises(AlerterLoadError):
        load_alerter(f"{__name__}:ThisClassDoesNotExist")


def test_load_alerter_raises_when_construction_fails() -> None:
    """An alerter whose constructor rejects the given kwargs (e.g. a
    typo'd config key) fails loudly rather than a raw TypeError
    leaking through unwrapped."""
    with pytest.raises(AlerterLoadError):
        load_alerter(f"{__name__}:_FixtureAlerter", unexpected_kwarg=True)
