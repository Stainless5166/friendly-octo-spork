"""Acceptance tests for the dynamic Alerter loader (docs/DESIGN.md §12.1).

Mirrors tests/core/providers/test_loader.py / tests/core/llm/test_loader.py
exactly — same import/instantiate mechanics, just for Alerter specs.
Uses a fixture class defined in this module, self-referenced via
__name__ — this is spork's own loading/error-wrapping logic under
test, not any concrete backend's behavior.
"""

from __future__ import annotations

import pytest

from spork.core.alerts.loader import AlerterLoadError, load_alerter


class _FixtureAlerter:
    """A minimal stand-in satisfying Alerter, used only to prove the
    loader's import/instantiate mechanics work — never a real backend."""

    def __init__(self, label: str = "default") -> None:
        self.label = label

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: str = "normal"
    ) -> None:  # pragma: no cover - never actually called
        raise NotImplementedError


def test_load_alerter_imports_and_instantiates_by_spec() -> None:
    """A well-formed "module:ClassName" spec resolves to an instance."""
    alerter = load_alerter(f"{__name__}:_FixtureAlerter")

    assert isinstance(alerter, _FixtureAlerter)
    assert alerter.label == "default"


def test_load_alerter_passes_through_constructor_kwargs() -> None:
    """Extra kwargs reach the alerter's constructor unmodified."""
    alerter = load_alerter(f"{__name__}:_FixtureAlerter", label="custom")

    assert alerter.label == "custom"


def test_load_alerter_raises_for_malformed_spec() -> None:
    """A spec with no ':' separator is rejected before any import is
    even attempted."""
    with pytest.raises(AlerterLoadError):
        load_alerter("no-colon-in-this-spec")
