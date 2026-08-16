"""FileProvider: a local-file Adapter to the Provider contract (§9.3).

Exists to prove the Provider/adapter abstraction generalizes beyond
JMAP with a second, *fully real* implementation — nothing here raises
NotImplementedError, unlike JmapProvider which is still blocked on a
live Fastmail session (docs/ROADMAP.md M1). It is explicitly not a
stand-in for "recent mail" from any live backend: spork has no local
mail store to substitute for one (docs/DESIGN.md §13), and this
doesn't pretend to be one either. It reads a literal, explicitly
supplied JSON file of messages, and on the write side appends every
applied action to a JSON-lines log — a real, inspectable backend in
its own right, useful for local dev/demo/CI work.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from spork.core.models import Attachment, NormalizedMessage
from spork.core.providers.base import (
    ActionApplier,
    AttachmentFetcher,
    BackfillPage,
    DraftCreator,
    KeywordApplier,
    MailboxLister,
    MessageLookup,
    MessageNotFoundError,
    ThreadContext,
    ThreadHistoryReader,
)
from spork.core.providers.file.attachments import load_attachments
from spork.core.providers.file.messages import load_messages
from spork.core.rules.schema import Action
from spork.core.sources.base import Source
from spork.core.sources.replay import ImmediateTrigger, SequenceContentFetcher
from spork.core.sources.triggered import TriggeredSource


class _FileActionApplier:
    """Appends each applied action to a JSON-lines log instead of mutating anything.

    There's no real mailbox underneath a FileProvider to move a
    message into — recording what *would* have happened, one JSON
    object per line, is the whole point (see this module's docstring).
    """

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        entry = {
            "message_id": message.message_id,
            "action_type": action.type,
            "mailbox": action.mailbox,
        }
        with self._log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")


class _FileKeywordApplier:
    """Appends each applied keyword set to its own JSON-lines log
    (docs/DESIGN.md §9.5, M10) — distinct from `_FileActionApplier`'s
    (a keyword isn't a mailbox action) and from `_FileDraftCreator`'s,
    same "separate logs stay independently inspectable" reasoning.
    """

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path

    def apply_keywords(self, message: NormalizedMessage, keywords: Sequence[str]) -> None:
        entry = {"message_id": message.message_id, "keywords": list(keywords)}
        with self._log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")


class _FileAttachmentFetcher:
    """Reads attachments from the same fixture file `build_source()`
    replays from (docs/DESIGN.md §9.5, M10) — real, inspectable data
    via `load_attachments()`, matching `_FileThreadHistoryReader`'s own
    "derive from the fixture" convention.
    """

    def __init__(self, attachments_by_message_id: dict[str, list[Attachment]]) -> None:
        self._attachments_by_message_id = attachments_by_message_id

    def fetch_attachments(self, message: NormalizedMessage) -> Sequence[Attachment]:
        return tuple(self._attachments_by_message_id.get(message.message_id, ()))


class _FileDraftCreator:
    """Appends each created draft to a JSON-lines log instead of creating
    anything real.

    A second, distinct log from `_FileActionApplier`'s — a draft isn't
    an action, and keeping them in separate files means either can be
    inspected without filtering the other out (docs/DESIGN.md §10.6).
    """

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path

    def create_draft(self, in_reply_to: NormalizedMessage, body: str) -> None:
        entry = {"in_reply_to_message_id": in_reply_to.message_id, "body": body}
        with self._log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")


class _FileThreadHistoryReader:
    """Derives thread history from the *other* messages already present
    in the same fixture file (docs/DESIGN.md §9.3) — real, inspectable
    data, not an invented placeholder.

    `prior_subject` is the earliest other message sharing `thread_id`
    (file order, matching `load_messages()`'s documented ordering
    guarantee); `user_has_replied` is whether any of them carries
    `"Sent"` in `mailbox_ids` — a message spork itself sent into that
    thread.
    """

    def __init__(self, messages: Sequence[NormalizedMessage]) -> None:
        self._messages = messages

    def get_thread_context(self, message: NormalizedMessage) -> ThreadContext:
        others = [
            m
            for m in self._messages
            if m.thread_id == message.thread_id and m.message_id != message.message_id
        ]
        prior_subject = others[0].subject if others else None
        user_has_replied = any("Sent" in m.mailbox_ids for m in others)
        return ThreadContext(prior_subject=prior_subject, user_has_replied=user_has_replied)


class _FileMailboxLister:
    """Returns a fixed, already-resolved mailbox list — either the
    explicit `available_mailboxes` a `FileProvider` was constructed
    with, or one derived from the fixture file itself (see
    `FileProvider.build_mailbox_lister()`); never invented here.
    """

    def __init__(self, mailboxes: Sequence[str]) -> None:
        self._mailboxes = mailboxes

    def list_mailboxes(self) -> Sequence[str]:
        return self._mailboxes


class _FileMessageLookup:
    """Scans the same fixture file `build_source()` replays from for a
    matching `message_id` (docs/DESIGN.md §7.4/§13, for `spork
    reclassify <id>`) — real, not a stand-in for `JmapClient.get_message()`'s
    eventual `Email/get` call.
    """

    def __init__(self, messages: Sequence[NormalizedMessage]) -> None:
        self._messages = messages

    def get_message(self, message_id: str) -> NormalizedMessage:
        for message in self._messages:
            if message.message_id == message_id:
                return message
        raise MessageNotFoundError(
            f"no message with id {message_id!r}; known ids: "
            f"{sorted(m.message_id for m in self._messages)}"
        )


class FileProvider:
    """Adapts a local JSON messages file to the `Provider` contract.

    `build_source()` replays every message in `messages_path` exactly
    once via `ImmediateTrigger` + `SequenceContentFetcher`
    (`spork.core.sources.replay`) — no polling, no push, just the
    fixed set of messages the file contains at the moment `poll()` is
    first called. `build_action_applier()`/`build_draft_creator()` are
    the write-side counterparts: both log to a JSON-lines file rather
    than mutating anything, since there's no real backend underneath
    to mutate. `drafts_log_path` defaults to `drafts.jsonl` next to
    `actions_log_path` when not given explicitly, so existing two-arg
    `FileProvider(messages_path, actions_log_path)` call sites keep
    working unchanged. `build_thread_history_reader()`/
    `build_mailbox_lister()` (docs/DESIGN.md §9.3) are real too: thread
    context comes from the other messages already in `messages_path`
    that share a `thread_id`; the mailbox list is `available_mailboxes`
    when given, or the sorted union of every message's `mailbox_ids`
    otherwise. `build_message_lookup()` (§7.4/§13) scans the same file
    for a matching `message_id`. `build_attachment_fetcher()` (§9.5,
    M10) reads each message's `"attachments"` array from the same
    file; `build_keyword_applier()` logs to its own `keywords.jsonl`,
    defaulting next to `actions_log_path` the same way
    `drafts_log_path` does.
    """

    def __init__(
        self,
        messages_path: str | Path,
        actions_log_path: str | Path,
        *,
        drafts_log_path: str | Path | None = None,
        keywords_log_path: str | Path | None = None,
        available_mailboxes: Sequence[str] | None = None,
    ) -> None:
        self._messages_path = Path(messages_path)
        self._actions_log_path = Path(actions_log_path)
        self._drafts_log_path = (
            Path(drafts_log_path)
            if drafts_log_path is not None
            else self._actions_log_path.with_name("drafts.jsonl")
        )
        self._keywords_log_path = (
            Path(keywords_log_path)
            if keywords_log_path is not None
            else self._actions_log_path.with_name("keywords.jsonl")
        )
        self._available_mailboxes = available_mailboxes

    def build_source(self) -> Source:
        messages = load_messages(self._messages_path)
        # batch_size = len(messages): a FileProvider has no notion of
        # "new since last poll" the way a live source does, so the
        # first poll() hands back everything the file contains, in one
        # batch, rather than trickling it out one message at a time.
        fetcher = SequenceContentFetcher(messages, batch_size=max(len(messages), 1))
        return TriggeredSource(ImmediateTrigger(), fetcher)

    def build_action_applier(self) -> ActionApplier:
        return _FileActionApplier(self._actions_log_path)

    def build_draft_creator(self) -> DraftCreator:
        return _FileDraftCreator(self._drafts_log_path)

    def build_thread_history_reader(self) -> ThreadHistoryReader:
        return _FileThreadHistoryReader(load_messages(self._messages_path))

    def build_mailbox_lister(self) -> MailboxLister:
        if self._available_mailboxes is not None:
            return _FileMailboxLister(self._available_mailboxes)
        messages = load_messages(self._messages_path)
        derived = sorted({mailbox_id for m in messages for mailbox_id in m.mailbox_ids})
        return _FileMailboxLister(derived)

    def build_message_lookup(self) -> MessageLookup:
        return _FileMessageLookup(load_messages(self._messages_path))

    def build_attachment_fetcher(self) -> AttachmentFetcher:
        return _FileAttachmentFetcher(load_attachments(self._messages_path))

    def build_keyword_applier(self) -> KeywordApplier:
        return _FileKeywordApplier(self._keywords_log_path)

    def query_messages(
        self, *, unread_only: bool = False, position: int = 0, limit: int = 50
    ) -> BackfillPage:
        """Page through `messages_path` in-process — no server-side query to delegate to.

        Proves `BackfillProvider` generalizes beyond JMAP the same way
        `Provider` itself does (§9.3, M1b): a real second implementation,
        not a stand-in. `unread_only` is accepted for interface parity
        but has nothing to filter on — a fixture file has no "seen"
        state — and is a no-op here, not silently misleading (still
        every message, every time).
        """
        del unread_only
        messages = load_messages(self._messages_path)
        total = len(messages)
        page = tuple(messages[position : position + limit])
        next_position = position + len(page)
        return BackfillPage(
            messages=page,
            position=position,
            next_position=next_position,
            total=total,
            has_more=next_position < total,
        )
