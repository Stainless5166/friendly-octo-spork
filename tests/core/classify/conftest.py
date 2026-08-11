"""Test isolation for spork.core.classify.registry's module-level state.

The registry is deliberately a plain module dict (docs/DESIGN.md §9.1) so
registering a backend is a one-liner; that convenience means registry
tests must restore it after themselves, or one test's registration would
silently leak into the next.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from spork.core.classify import registry


@pytest.fixture(autouse=True)
def _isolated_registry() -> Iterator[None]:
    """Snapshot the registry before each test in this package, restore after."""
    original = dict(registry._REGISTRY)
    try:
        yield
    finally:
        registry._REGISTRY.clear()
        registry._REGISTRY.update(original)
