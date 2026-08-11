"""Acceptance tests for primary/secondary Source fallback (docs/DESIGN.md
§8's "poll-based fallback when push is unavailable/disconnected").

Expressed generically over any two Sources (not JMAP-specific) so it's
exercised here with plain stub sources — no live push/poll connection
involved.
"""

from __future__ import annotations

import pytest

from spork.core.models import NormalizedMessage
from spork.core.sources.fallback import FallbackSource


class _FixedSource:
    def __init__(self, messages: list[NormalizedMessage]) -> None:
        self._messages = messages

    def poll(self) -> list[NormalizedMessage]:
        return self._messages


class _FailingSource:
    def poll(self) -> list[NormalizedMessage]:
        raise ConnectionError("simulated push disconnect")


def test_fallback_uses_primary_when_it_succeeds(make_message) -> None:
    """When the primary source works, its result is used directly —
    the secondary is never touched."""
    primary_messages = [make_message(message_id="from-primary")]
    source = FallbackSource(_FixedSource(primary_messages), _FailingSource())

    assert source.poll() == primary_messages


def test_fallback_switches_to_secondary_when_primary_raises(make_message) -> None:
    """A primary that raises falls back to the secondary's result
    instead of propagating the error — the whole point of a fallback."""
    secondary_messages = [make_message(message_id="from-secondary")]
    source = FallbackSource(_FailingSource(), _FixedSource(secondary_messages))

    assert source.poll() == secondary_messages


def test_fallback_retries_primary_on_the_next_poll_call(make_message) -> None:
    """After falling back once, the next poll() tries primary again —
    a recovered push connection is used again automatically, without
    anything needing to notice and switch back explicitly."""
    calls = {"primary": 0}

    class RecoveringSource:
        def poll(self) -> list[NormalizedMessage]:
            calls["primary"] += 1
            if calls["primary"] == 1:
                raise ConnectionError("simulated disconnect on first poll only")
            return [make_message(message_id="from-recovered-primary")]

    source = FallbackSource(RecoveringSource(), _FixedSource([make_message(message_id="fallback")]))

    first = source.poll()
    second = source.poll()

    assert [m.message_id for m in first] == ["fallback"]
    assert [m.message_id for m in second] == ["from-recovered-primary"]


def test_fallback_only_catches_configured_exception_types(make_message) -> None:
    """`catch` narrows which primary exceptions trigger a fallback — an
    exception type not in that set propagates instead of being
    silently swallowed and hidden behind the secondary's result."""
    source = FallbackSource(
        _FailingSource(),
        _FixedSource([make_message()]),
        catch=(TimeoutError,),
    )

    with pytest.raises(ConnectionError):
        source.poll()
