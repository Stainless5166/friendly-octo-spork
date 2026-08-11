"""Failure/edge-case tests for the dynamic provider loader.

Companion to test_loader.py's acceptance tests.
"""

from __future__ import annotations

import pytest

from spork.core.providers.loader import ProviderLoadError, load_provider


class _FixtureProvider:
    def __init__(self, label: str = "default") -> None:
        self.label = label

    def build_source(self) -> None:  # pragma: no cover - never actually called
        raise NotImplementedError


def test_load_provider_raises_for_unimportable_module() -> None:
    """A spec naming a module that doesn't exist fails loudly rather
    than a raw ImportError leaking through unwrapped."""
    with pytest.raises(ProviderLoadError):
        load_provider("this.module.does.not.exist:Whatever")


def test_load_provider_raises_for_missing_class_attribute() -> None:
    """A spec naming a real module but a class that isn't defined
    there fails loudly rather than a raw AttributeError leaking
    through unwrapped."""
    with pytest.raises(ProviderLoadError):
        load_provider(f"{__name__}:ThisClassDoesNotExist")


def test_load_provider_raises_when_construction_fails() -> None:
    """A provider whose constructor rejects the given kwargs (e.g. a
    typo'd config key) fails loudly rather than a raw TypeError
    leaking through unwrapped."""
    with pytest.raises(ProviderLoadError):
        load_provider(f"{__name__}:_FixtureProvider", unexpected_kwarg=True)
