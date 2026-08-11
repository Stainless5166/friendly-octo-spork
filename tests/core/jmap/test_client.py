"""Spec tests for JmapClient (docs/ROADMAP.md M1), catching its
deliberate NotImplementedError placeholders.

connect() and fetch_new_messages() both require a real jmapc session
against a live Fastmail account — not something unit tests (or this
environment) can exercise honestly. Rather than leaving the class
unspecified until that's possible, this locks in its shape
(constructor args, method names/signatures) now, and asserts each
method raises a clear, catchable NotImplementedError rather than doing
nothing or silently pretending to succeed. These are ordinary passing
tests, not xfail — the "not implemented" behavior itself is the
correct, specified behavior at this stage.
"""

from __future__ import annotations

import pytest

from spork.core.jmap.client import JmapClient


def test_connect_raises_not_implemented() -> None:
    """connect() would establish a real jmapc session — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.connect()


def test_fetch_new_messages_raises_not_implemented() -> None:
    """fetch_new_messages() would batch Email/query + Email/get against
    a live session — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.fetch_new_messages(since_cursor=None)
