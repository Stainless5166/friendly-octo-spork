"""Acceptance tests for the dynamic LLMClient loader (docs/DESIGN.md §10.1).

Mirrors tests/core/providers/test_loader.py exactly — same
import/instantiate mechanics, just for LLMClient specs instead of
Provider ones. Uses a fixture class defined in this module,
self-referenced via __name__ — this is spork's own loading/
error-wrapping logic under test, not any concrete client's behavior.
"""

from __future__ import annotations

import pytest

from spork.core.llm.base import Verdict, VerdictRequest
from spork.core.llm.loader import LLMClientLoadError, load_llm_client


class _FixtureClient:
    """A minimal stand-in satisfying LLMClient, used only to prove the
    loader's import/instantiate mechanics work — never a real backend."""

    def __init__(self, label: str = "default") -> None:
        self.label = label

    def get_verdict(self, request: VerdictRequest) -> Verdict:  # pragma: no cover - never called
        raise NotImplementedError


def test_load_llm_client_imports_and_instantiates_by_spec() -> None:
    """A well-formed "module:ClassName" spec resolves to an instance."""
    client = load_llm_client(f"{__name__}:_FixtureClient")

    assert isinstance(client, _FixtureClient)
    assert client.label == "default"


def test_load_llm_client_passes_through_constructor_kwargs() -> None:
    """Extra kwargs reach the client's constructor unmodified."""
    client = load_llm_client(f"{__name__}:_FixtureClient", label="custom")

    assert client.label == "custom"


def test_load_llm_client_raises_for_malformed_spec() -> None:
    """A spec with no ':' separator is rejected before any import is
    even attempted."""
    with pytest.raises(LLMClientLoadError):
        load_llm_client("no-colon-in-this-spec")
