"""Failure/edge-case tests for FallbackSource.

Companion to test_fallback.py's acceptance tests.
"""

from __future__ import annotations

import pytest

from spork.core.models import NormalizedMessage
from spork.core.sources.fallback import FallbackSource


class _FailingSource:
    def poll(self) -> list[NormalizedMessage]:
        raise ConnectionError("simulated failure")


def test_fallback_propagates_when_both_primary_and_secondary_fail() -> None:
    """If the secondary also raises, that exception propagates rather
    than being silently swallowed — a fallback source has nothing left
    to fall back to at that point."""
    source = FallbackSource(_FailingSource(), _FailingSource())

    with pytest.raises(ConnectionError):
        source.poll()


def test_fallback_does_not_catch_baseexception_subclasses() -> None:
    """The default catch=(Exception,) must never swallow something like
    KeyboardInterrupt or SystemExit — those aren't Exception subclasses
    and a daemon should never accidentally suppress a shutdown signal
    just because it looks similar to a connection error."""

    class InterruptingSource:
        def poll(self) -> list[NormalizedMessage]:
            raise KeyboardInterrupt

    source = FallbackSource(InterruptingSource(), _FailingSource())

    with pytest.raises(KeyboardInterrupt):
        source.poll()
