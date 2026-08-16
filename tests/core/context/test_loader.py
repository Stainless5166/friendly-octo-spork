"""Acceptance tests for the dynamic ContextProvider loader (docs/DESIGN.md §10.8).

Mirrors tests/core/llm/test_loader.py exactly — same import/instantiate
mechanics, just for ContextProvider specs.
"""

from __future__ import annotations

import pytest

from spork.core.context.base import ContextResult
from spork.core.context.loader import ContextProviderLoadError, load_context_provider


class _FixtureContextProvider:
    """A minimal stand-in satisfying ContextProvider, used only to
    prove the loader's import/instantiate mechanics work — never a
    real backend."""

    def __init__(self, label: str = "default") -> None:
        self.label = label

    def get_context(self, message: object) -> ContextResult:  # pragma: no cover - never called
        raise NotImplementedError


def test_load_context_provider_imports_and_instantiates_by_spec() -> None:
    provider = load_context_provider(f"{__name__}:_FixtureContextProvider")

    assert isinstance(provider, _FixtureContextProvider)
    assert provider.label == "default"


def test_load_context_provider_passes_through_constructor_kwargs() -> None:
    provider = load_context_provider(f"{__name__}:_FixtureContextProvider", label="custom")

    assert provider.label == "custom"


def test_load_context_provider_raises_for_malformed_spec() -> None:
    with pytest.raises(ContextProviderLoadError):
        load_context_provider("no-colon-in-this-spec")


def test_load_context_provider_raises_for_an_unimportable_module() -> None:
    with pytest.raises(ContextProviderLoadError):
        load_context_provider("spork.core.context.nonexistent_module:Whatever")


def test_load_context_provider_raises_for_a_missing_class() -> None:
    with pytest.raises(ContextProviderLoadError):
        load_context_provider(f"{__name__}:NoSuchClass")
