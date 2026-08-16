"""Failure/edge-case tests for the ContextProvider loader.

Companion to test_loader.py's acceptance tests.
"""

from __future__ import annotations

import pytest

from spork.core.context.loader import ContextProviderLoadError, load_context_provider


class _FixtureContextProvider:
    def __init__(self, label: str = "default") -> None:
        self.label = label


def test_load_context_provider_raises_when_construction_fails() -> None:
    """A provider whose constructor rejects the given kwargs (e.g. a
    typo'd config key) fails loudly rather than a raw TypeError
    leaking through unwrapped."""
    with pytest.raises(ContextProviderLoadError):
        load_context_provider(f"{__name__}:_FixtureContextProvider", unexpected_kwarg=True)
