"""Acceptance tests for JmapProvider, the JMAP Adapter (docs/DESIGN.md §9.3).

JmapClient/JmapPushTrigger are still NotImplementedError stubs (they
need a live Fastmail session — docs/ROADMAP.md M1), so these tests
only cover composition: does build_source() assemble the right pieces,
and does the resulting Source correctly propagate the underlying
stub's NotImplementedError when actually used.
"""

from __future__ import annotations

import pytest
from spork.core.providers.jmap.provider import JmapProvider

from spork.core.sources.triggered import TriggeredSource


def test_build_source_returns_a_triggered_source() -> None:
    """build_source() composes a JmapPushTrigger + JMAP fetcher via
    TriggeredSource — the same composition any Source consumer expects
    from docs/DESIGN.md §9.2, not a bespoke JMAP-only shape."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")

    source = provider.build_source()

    assert isinstance(source, TriggeredSource)


def test_source_poll_raises_not_implemented() -> None:
    """Polling the composed Source raises NotImplementedError, propagated
    from JmapPushTrigger.wait() — proving JmapProvider actually wires the
    real (if still-stubbed) pieces together, not placeholders of its own."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")
    source = provider.build_source()

    with pytest.raises(NotImplementedError):
        source.poll()
