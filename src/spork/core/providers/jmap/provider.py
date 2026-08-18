"""JmapProvider: the Adapter from JMAP to the common Provider contract (§9.3).

Composes pieces that already exist (`JmapClient`, `JmapPushTrigger`,
`TriggeredSource`) rather than reimplementing any fetch/push/mutate
logic — this module's only job is presenting them as `Provider`'s
read (`Source`) and write (`ActionApplier`) sides.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from spork.core.models import Attachment, NormalizedMessage
from spork.core.providers.base import (
    ActionApplier,
    AttachmentFetcher,
    BackfillPage,
    DraftCreator,
    KeywordApplier,
    MailboxLister,
    MessageLookup,
    ThreadContext,
    ThreadHistoryReader,
)
from spork.core.providers.jmap.client import JmapClient, JmapFetchResult
from spork.core.providers.jmap.push import JmapPushDisconnectedError, JmapPushTrigger
from spork.core.rules.schema import Action
from spork.core.sources.base import CheckpointedSource, MessageBatch, Source, Trigger
from spork.core.sources.fallback import CheckpointedFallbackSource
from spork.core.sources.timer import IntervalTimer
from spork.core.sources.triggered import TriggeredSource


class _FetchClient(Protocol):
    """The read leaf needed by the temporary TriggeredSource adapter."""

    def fetch_new_messages(self, since_cursor: str | None) -> JmapFetchResult: ...


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

    def __init__(self, client: _FetchClient, *, cursor: str | None = None) -> None:
        self._client = client
        self._cursor = cursor

    def fetch(self) -> Sequence[NormalizedMessage]:
        return self._client.fetch_new_messages(since_cursor=self._cursor).messages


@dataclass
class _JmapCursorState:
    value: str | None


class _JmapCheckpointedSource:
    """Push-triggered JMAP source that exposes a candidate Email state."""

    def __init__(
        self,
        client: JmapClient,
        cursor: str | None,
        *,
        trigger: Trigger | None = None,
        cursor_state: _JmapCursorState | None = None,
    ) -> None:
        self._client = client
        self._cursor_state = cursor_state or _JmapCursorState(cursor)
        self._trigger = trigger if trigger is not None else JmapPushTrigger(client)

    def poll_batch(self) -> MessageBatch:
        self._trigger.wait()
        result = self._client.fetch_new_messages(since_cursor=self._cursor_state.value)
        self._cursor_state.value = result.cursor
        return MessageBatch(messages=result.messages, checkpoint=result.cursor)

    def poll(self) -> Sequence[NormalizedMessage]:
        """Expose the ordinary Source view for generic callers."""
        return self.poll_batch().messages


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


class _JmapAttachmentFetcher:
    """Adapts `JmapClient.fetch_attachments()` to the `AttachmentFetcher`
    contract (docs/DESIGN.md §9.5, M10). A pure delegation, same shape
    as `_JmapActionApplier`.
    """

    def __init__(self, client: JmapClient) -> None:
        self._client = client

    def fetch_attachments(self, message: NormalizedMessage) -> Sequence[Attachment]:
        return self._client.fetch_attachments(message)


class _JmapKeywordApplier:
    """Adapts `JmapClient.apply_keywords()` to the `KeywordApplier`
    contract (docs/DESIGN.md §9.5, M10). A pure delegation, same shape
    as `_JmapActionApplier`.
    """

    def __init__(self, client: JmapClient) -> None:
        self._client = client

    def apply_keywords(self, message: NormalizedMessage, keywords: Sequence[str]) -> None:
        self._client.apply_keywords(message, keywords)


class JmapProvider:
    """Adapts a JMAP account to the `Provider` contract.

    `build_source()` composes `JmapPushTrigger` (the trigger) and a
    `JmapClient`-backed fetcher (the content) via `TriggeredSource` —
    exactly the split docs/DESIGN.md §9.2 describes for JMAP.
    `build_action_applier()`/`build_draft_creator()` are the write-side
    counterparts (§9.3, §10.6): all three are assembled here once
    instead of duplicated at every call site.
    """

    def __init__(
        self,
        host: str,
        api_token: str,
        *,
        cursor: str | None = None,
        poll_interval_seconds: float = 300.0,
        reconnect_backoff_seconds: Sequence[float] = (2.0, 5.0, 15.0, 60.0, 300.0),
        allow_writes: bool = False,
    ) -> None:
        self._client = JmapClient(host=host, api_token=api_token, allow_writes=allow_writes)
        self._cursor = cursor
        self._poll_interval_seconds = poll_interval_seconds
        self._reconnect_backoff_seconds = tuple(reconnect_backoff_seconds)

    def build_source(self) -> Source:
        trigger = JmapPushTrigger(self._client)
        fetcher = _JmapContentFetcher(self._client, cursor=self._cursor)
        return TriggeredSource(trigger, fetcher)

    def account_id(self) -> str:
        """Connect before readiness and identify the StateDB cursor row."""
        return self._client.account_id

    def build_checkpointed_source(self, cursor: str | None) -> CheckpointedSource:
        """Build the JMAP source using the daemon's acknowledged cursor."""
        cursor_state = _JmapCursorState(cursor)
        primary = _JmapCheckpointedSource(
            self._client,
            cursor,
            cursor_state=cursor_state,
            trigger=JmapPushTrigger(
                self._client,
                account_id=self._client.account_id,
                reconnect_backoff=self._reconnect_backoff_seconds,
            ),
        )
        secondary = _JmapCheckpointedSource(
            self._client,
            cursor,
            cursor_state=cursor_state,
            trigger=IntervalTimer(self._poll_interval_seconds),
        )
        return CheckpointedFallbackSource(
            primary,
            secondary,
            catch=(JmapPushDisconnectedError,),
        )

    def build_action_applier(self) -> ActionApplier:
        return _JmapActionApplier(self._client)

    def query_messages(
        self, *, unread_only: bool = False, position: int = 0, limit: int = 50
    ) -> BackfillPage:
        """Delegate to `JmapClient.query_messages()`, wrapped as the
        backend-agnostic `BackfillPage` (§9.3, M8) rather than the
        JMAP-specific `JmapQueryResult` — same reasoning as every other
        `build_*()` method here, presenting jmapc-adjacent types under
        the shape `Provider` consumers expect."""
        result = self._client.query_messages(
            unread_only=unread_only, position=position, limit=limit
        )
        return BackfillPage(
            messages=result.messages,
            position=result.position,
            next_position=result.next_position,
            total=result.total,
            has_more=result.has_more,
        )

    def build_draft_creator(self) -> DraftCreator:
        return _JmapDraftCreator(self._client)

    def build_thread_history_reader(self) -> ThreadHistoryReader:
        return _JmapThreadHistoryReader(self._client)

    def build_mailbox_lister(self) -> MailboxLister:
        return _JmapMailboxLister(self._client)

    def build_message_lookup(self) -> MessageLookup:
        return _JmapMessageLookup(self._client)

    def build_attachment_fetcher(self) -> AttachmentFetcher:
        return _JmapAttachmentFetcher(self._client)

    def build_keyword_applier(self) -> KeywordApplier:
        return _JmapKeywordApplier(self._client)
