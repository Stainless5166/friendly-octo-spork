"""Acceptance tests for the dynamic provider loader (docs/DESIGN.md §9.3).

Uses a fixture class defined in this module, self-referenced via
__name__ — this is spork's own loading/error-wrapping logic under
test, not any concrete provider's behavior.
"""

from __future__ import annotations

import pytest
from spork.core.providers.loader import ProviderLoadError, load_provider


class _FixtureProvider:
    """A minimal stand-in satisfying Provider, used only to prove the
    loader's import/instantiate mechanics work — never a real backend."""

    def __init__(self, label: str = "default") -> None:
        self.label = label

    def build_source(self) -> None:  # pragma: no cover - never actually called
        raise NotImplementedError


def test_load_provider_imports_and_instantiates_by_spec() -> None:
    """A well-formed "module:ClassName" spec resolves to an instance."""
    provider = load_provider(f"{__name__}:_FixtureProvider")

    assert isinstance(provider, _FixtureProvider)
    assert provider.label == "default"


def test_load_provider_passes_through_constructor_kwargs() -> None:
    """Extra kwargs reach the provider's constructor unmodified."""
    provider = load_provider(f"{__name__}:_FixtureProvider", label="custom")

    assert provider.label == "custom"


def test_load_provider_raises_for_malformed_spec() -> None:
    """A spec with no ':' separator is rejected before any import is
    even attempted."""
    with pytest.raises(ProviderLoadError):
        load_provider("no-colon-in-this-spec")
