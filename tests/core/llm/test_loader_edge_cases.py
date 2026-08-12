"""Failure/edge-case tests for the dynamic LLMClient loader.

Companion to test_loader.py's acceptance tests. Mirrors
tests/core/providers/test_loader_edge_cases.py.
"""

from __future__ import annotations

import pytest

from spork.core.llm.base import Verdict, VerdictRequest
from spork.core.llm.loader import LLMClientLoadError, load_llm_client


class _FixtureClient:
    def __init__(self, label: str = "default") -> None:
        self.label = label

    def get_verdict(self, request: VerdictRequest) -> Verdict:  # pragma: no cover - never called
        raise NotImplementedError


def test_load_llm_client_raises_for_unimportable_module() -> None:
    """A spec naming a module that doesn't exist fails loudly rather
    than a raw ImportError leaking through unwrapped."""
    with pytest.raises(LLMClientLoadError):
        load_llm_client("this.module.does.not.exist:Whatever")


def test_load_llm_client_raises_for_missing_class_attribute() -> None:
    """A spec naming a real module but a class that isn't defined
    there fails loudly rather than a raw AttributeError leaking
    through unwrapped."""
    with pytest.raises(LLMClientLoadError):
        load_llm_client(f"{__name__}:ThisClassDoesNotExist")


def test_load_llm_client_raises_when_construction_fails() -> None:
    """A client whose constructor rejects the given kwargs (e.g. a
    typo'd config key) fails loudly rather than a raw TypeError
    leaking through unwrapped."""
    with pytest.raises(LLMClientLoadError):
        load_llm_client(f"{__name__}:_FixtureClient", unexpected_kwarg=True)
