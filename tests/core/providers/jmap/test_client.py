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

from spork.core.providers.jmap.client import JmapClient
from spork.core.rules.schema import Action


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


def test_apply_action_raises_not_implemented(make_message) -> None:
    """apply_action() would mutate the mailbox via Email/set against a
    live session (docs/DESIGN.md §9.3) — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.apply_action(make_message(), Action(type="move", mailbox="Reading"))


def test_create_draft_raises_not_implemented(make_message) -> None:
    """create_draft() would create a draft via Email/set into Drafts
    against a live session (docs/DESIGN.md §10.6) — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.create_draft(make_message(), "Friday 2pm works for me.")


def test_get_thread_context_raises_not_implemented(make_message) -> None:
    """get_thread_context() would search a live session's thread history
    via Email/query (docs/DESIGN.md §9.3) — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.get_thread_context(make_message())


def test_list_mailboxes_raises_not_implemented() -> None:
    """list_mailboxes() would fetch Mailbox/get against a live session
    (docs/DESIGN.md §9.3) — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.list_mailboxes()


def test_get_message_raises_not_implemented() -> None:
    """get_message() would fetch one message by id via Email/get
    against a live session (docs/DESIGN.md §9.3, for spork reclassify)
    — not built yet."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")

    with pytest.raises(NotImplementedError):
        client.get_message("msg-1")
