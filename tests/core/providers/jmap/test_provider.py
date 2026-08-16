"""Acceptance tests for JmapProvider, the JMAP Adapter (docs/DESIGN.md §9.3).

JmapClient/JmapPushTrigger are still NotImplementedError stubs (they
need a live Fastmail session — docs/ROADMAP.md M1), so these tests
only cover composition: does build_source() assemble the right pieces,
and does the resulting Source correctly propagate the underlying
stub's NotImplementedError when actually used.
"""

from __future__ import annotations

import pytest

from spork.core.providers.base import ThreadContext
from spork.core.providers.jmap.client import JmapClient, JmapFetchResult
from spork.core.providers.jmap.provider import (
    JmapProvider,
    _JmapActionApplier,
    _JmapCheckpointedSource,
    _JmapContentFetcher,
    _JmapDraftCreator,
    _JmapMailboxLister,
    _JmapMessageLookup,
    _JmapThreadHistoryReader,
)
from spork.core.providers.jmap.push import JmapPushDisconnectedError, JmapPushTrigger
from spork.core.rules.schema import Action
from spork.core.sources.fallback import CheckpointedFallbackSource
from spork.core.sources.triggered import TriggeredSource


def test_build_source_returns_a_triggered_source() -> None:
    """build_source() composes a JmapPushTrigger + JMAP fetcher via
    TriggeredSource — the same composition any Source consumer expects
    from docs/DESIGN.md §9.2, not a bespoke JMAP-only shape."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")

    source = provider.build_source()

    assert isinstance(source, TriggeredSource)


def test_source_poll_propagates_a_transient_push_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ordinary source view preserves the push boundary error."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")
    source = provider.build_source()

    def disconnected(self: JmapPushTrigger) -> None:
        raise JmapPushDisconnectedError("disconnected")

    monkeypatch.setattr(JmapPushTrigger, "wait", disconnected)

    with pytest.raises(JmapPushDisconnectedError, match="disconnected"):
        source.poll()


def test_content_fetcher_returns_messages_from_the_clients_candidate_batch(
    make_message,
) -> None:
    """The temporary TriggeredSource adapter unwraps messages while the
    cursor-safe daemon acknowledgement path is built in the next unit."""
    message = make_message()
    cursors: list[str | None] = []

    class _Client:
        def fetch_new_messages(self, since_cursor: str | None) -> JmapFetchResult:
            cursors.append(since_cursor)
            return JmapFetchResult(messages=(message,), cursor="state-2")

    fetcher = _JmapContentFetcher(_Client(), cursor="state-1")

    assert fetcher.fetch() == (message,)


def test_checkpointed_source_exposes_the_clients_candidate_state(make_message) -> None:
    message = make_message()
    cursors: list[str | None] = []

    class _Client(JmapClient):
        def __init__(self) -> None:
            pass

        def fetch_new_messages(self, since_cursor: str | None) -> JmapFetchResult:
            cursors.append(since_cursor)
            return JmapFetchResult(messages=(message,), cursor="state-2")

    class _Trigger:
        def wait(self) -> None:
            pass

    source = _JmapCheckpointedSource(_Client(), "state-1", trigger=_Trigger())

    batch = source.poll_batch()

    assert batch.messages == (message,)
    assert batch.checkpoint == "state-2"
    assert source.poll() == (message,)
    assert cursors == ["state-1", "state-2"]


def test_provider_builds_a_checkpointed_source_and_exposes_account_id() -> None:
    class _Client(JmapClient):
        def __init__(self) -> None:
            pass

        @property
        def account_id(self) -> str:
            return "account-1"

    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")
    provider._client = _Client()

    source = provider.build_checkpointed_source("state-1")

    assert isinstance(source, CheckpointedFallbackSource)
    assert provider.account_id() == "account-1"


def test_build_action_applier_returns_something_that_can_apply(make_message) -> None:
    """build_action_applier() returns an object satisfying ActionApplier
    (has an .apply() method) — the write half of the Provider contract,
    per docs/DESIGN.md §9.3's "read and write are the same relationship"."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")

    applier = provider.build_action_applier()

    with pytest.raises(NotImplementedError):
        applier.apply(make_message(), Action(type="move", mailbox="Reading"))


def test_action_applier_delegates_to_the_client_directly(make_message) -> None:
    """The applier is a real delegation to JmapClient.apply_action(),
    not a second placeholder — mirrors
    test_content_fetcher_delegates_to_the_client_directly."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")
    applier = _JmapActionApplier(client)

    with pytest.raises(NotImplementedError):
        applier.apply(make_message(), Action(type="tag", mailbox="Urgent"))


def test_build_draft_creator_returns_something_that_can_create_a_draft(make_message) -> None:
    """build_draft_creator() returns an object satisfying DraftCreator
    (has a .create_draft() method) — the third leg of the Provider
    contract per docs/DESIGN.md §10.6."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")

    draft_creator = provider.build_draft_creator()

    with pytest.raises(NotImplementedError):
        draft_creator.create_draft(make_message(), "Friday 2pm works for me.")


def test_draft_creator_delegates_to_the_client_directly(make_message) -> None:
    """The draft creator is a real delegation to JmapClient.create_draft(),
    not a second placeholder — mirrors
    test_action_applier_delegates_to_the_client_directly."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")
    draft_creator = _JmapDraftCreator(client)

    with pytest.raises(NotImplementedError):
        draft_creator.create_draft(make_message(), "Friday 2pm works for me.")


def test_build_thread_history_reader_returns_something_that_can_get_context(
    make_message, monkeypatch
) -> None:
    """build_thread_history_reader() returns an object satisfying
    ThreadHistoryReader — the fourth leg of the Provider contract per
    docs/DESIGN.md §9.3, needed to wire Tier 2 into the daemon loop."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")

    reader = provider.build_thread_history_reader()

    expected = ThreadContext(prior_subject="Earlier", user_has_replied=True)
    monkeypatch.setattr(JmapClient, "get_thread_context", lambda self, message: expected)

    assert reader.get_thread_context(make_message()) == expected


def test_thread_history_reader_delegates_to_the_client_directly(make_message, monkeypatch) -> None:
    """The thread history reader is a real delegation to
    JmapClient.get_thread_context(), not a second placeholder — mirrors
    test_action_applier_delegates_to_the_client_directly."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")
    reader = _JmapThreadHistoryReader(client)

    expected = ThreadContext(prior_subject=None, user_has_replied=False)
    monkeypatch.setattr(JmapClient, "get_thread_context", lambda self, message: expected)

    assert reader.get_thread_context(make_message()) == expected


def test_build_mailbox_lister_returns_something_that_can_list_mailboxes(monkeypatch) -> None:
    """build_mailbox_lister() returns an object satisfying MailboxLister
    — the fifth leg of the Provider contract per docs/DESIGN.md §9.3."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")

    lister = provider.build_mailbox_lister()

    monkeypatch.setattr(JmapClient, "list_mailboxes", lambda self: ["Inbox", "Sent"])

    assert lister.list_mailboxes() == ["Inbox", "Sent"]


def test_mailbox_lister_delegates_to_the_client_directly(monkeypatch) -> None:
    """The mailbox lister is a real delegation to
    JmapClient.list_mailboxes(), not a second placeholder — mirrors
    test_action_applier_delegates_to_the_client_directly."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")
    lister = _JmapMailboxLister(client)

    monkeypatch.setattr(JmapClient, "list_mailboxes", lambda self: ["Archive"])

    assert lister.list_mailboxes() == ["Archive"]


def test_build_message_lookup_returns_something_that_can_get_a_message(
    make_message, monkeypatch
) -> None:
    """build_message_lookup() returns an object satisfying MessageLookup
    — the sixth leg of the Provider contract, for docs/DESIGN.md §13's
    spork reclassify <id>."""
    provider = JmapProvider(host="api.fastmail.com", api_token="fake-token")

    lookup = provider.build_message_lookup()

    expected = make_message(message_id="msg-1")
    monkeypatch.setattr(JmapClient, "get_message", lambda self, message_id: expected)

    assert lookup.get_message("msg-1") == expected


def test_message_lookup_delegates_to_the_client_directly(make_message, monkeypatch) -> None:
    """The message lookup is a real delegation to
    JmapClient.get_message(), not a second placeholder — mirrors
    test_action_applier_delegates_to_the_client_directly."""
    client = JmapClient(host="api.fastmail.com", api_token="fake-token")
    lookup = _JmapMessageLookup(client)

    expected = make_message(message_id="msg-1")
    monkeypatch.setattr(JmapClient, "get_message", lambda self, message_id: expected)

    assert lookup.get_message("msg-1") == expected
