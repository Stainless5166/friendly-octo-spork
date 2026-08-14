"""JmapProvider: the Adapter from JMAP to the common Provider contract (§9.3).

Composes pieces that already exist (`JmapClient`, `JmapPushTrigger`,
`TriggeredSource`) rather than reimplementing any fetch/push/mutate
logic — this module's only job is presenting them as `Provider`'s
read (`Source`) and write (`ActionApplier`) sides.
"""

from __future__ import annotations

from collections.abc import Sequence

from spork.core.models import NormalizedMessage
from spork.core.providers.base import (
    ActionApplier,
    DraftCreator,
    MailboxLister,
    MessageLookup,
    ThreadContext,
    ThreadHistoryReader,
)
from spork.core.providers.jmap.client import JmapClient
from spork.core.providers.jmap.push import JmapPushTrigger
from spork.core.rules.schema import Action
from spork.core.sources.base import Source
from spork.core.sources.triggered import TriggeredSource


class _JmapContentFetcher:
    """Adapts `JmapClient.fetch_new_messages()` to the `ContentFetcher` contract.

    Holds the starting cursor (typically `StateDB.get_cursor()`'s
    result) so `JmapProvider` callers don't need to know `JmapClient`'s
    fetch signature. Cursor *advancement* is real integration work that
    lands once `fetch_new_messages()` itself returns something to
    advance from — it's a `NotImplementedError` stub today (see
    `spork.core.providers.jmap.client`), so there's nothing to advance
    yet; this class isn't pretending otherwise.
    """

    def __init__(self, client: JmapClient, *, cursor: str | None = None) -> None:
        self._client = client
        self._cursor = cursor

    def fetch(self) -> Sequence[NormalizedMessage]:
        return self._client.fetch_new_messages(since_cursor=self._cursor)


class _JmapActionApplier:
    """Adapts `JmapClient.apply_action()` to the `ActionApplier` contract.

    A pure delegation, same shape as `_JmapContentFetcher` — no logic
    of its own beyond presenting `JmapClient`'s method under the name
    `ActionApplier` expects.
    """

    def __init__(self, client: JmapClient) -> None:
        self._client = client

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self._client.apply_action(message, action)


class _JmapDraftCreator:
    """Adapts `JmapClient.create_draft()` to the `DraftCreator` contract.

    A pure delegation, same shape as `_JmapActionApplier` — no logic
    of its own beyond presenting `JmapClient`'s method under the name
    `DraftCreator` expects.
    """

    def __init__(self, client: JmapClient) -> None:
        self._client = client

    def create_draft(self, in_reply_to: NormalizedMessage, body: str) -> None:
        self._client.create_draft(in_reply_to, body)


class _JmapThreadHistoryReader:
    """Adapts `JmapClient.get_thread_context()` to the `ThreadHistoryReader`
    contract. A pure delegation, same shape as `_JmapActionApplier`.
    """

    def __init__(self, client: JmapClient) -> None:
        self._client = client

    def get_thread_context(self, message: NormalizedMessage) -> ThreadContext:
        return self._client.get_thread_context(message)


class _JmapMailboxLister:
    """Adapts `JmapClient.list_mailboxes()` to the `MailboxLister`
    contract. A pure delegation, same shape as `_JmapActionApplier`.
    """

    def __init__(self, client: JmapClient) -> None:
        self._client = client

    def list_mailboxes(self) -> Sequence[str]:
        return self._client.list_mailboxes()


class _JmapMessageLookup:
    """Adapts `JmapClient.get_message()` to the `MessageLookup`
    contract. A pure delegation, same shape as `_JmapActionApplier`.
    """

    def __init__(self, client: JmapClient) -> None:
        self._client = client

    def get_message(self, message_id: str) -> NormalizedMessage:
        return self._client.get_message(message_id)


class JmapProvider:
    """Adapts a JMAP account to the `Provider` contract.

    `build_source()` composes `JmapPushTrigger` (the trigger) and a
    `JmapClient`-backed fetcher (the content) via `TriggeredSource` —
    exactly the split docs/DESIGN.md §9.2 describes for JMAP.
    `build_action_applier()`/`build_draft_creator()` are the write-side
    counterparts (§9.3, §10.6): all three are assembled here once
    instead of duplicated at every call site.
    """

    def __init__(self, host: str, api_token: str, *, cursor: str | None = None) -> None:
        self._client = JmapClient(host=host, api_token=api_token)
        self._cursor = cursor

    def build_source(self) -> Source:
        trigger = JmapPushTrigger(self._client)
        fetcher = _JmapContentFetcher(self._client, cursor=self._cursor)
        return TriggeredSource(trigger, fetcher)

    def build_action_applier(self) -> ActionApplier:
        return _JmapActionApplier(self._client)

    def build_draft_creator(self) -> DraftCreator:
        return _JmapDraftCreator(self._client)

    def build_thread_history_reader(self) -> ThreadHistoryReader:
        return _JmapThreadHistoryReader(self._client)

    def build_mailbox_lister(self) -> MailboxLister:
        return _JmapMailboxLister(self._client)

    def build_message_lookup(self) -> MessageLookup:
        return _JmapMessageLookup(self._client)
