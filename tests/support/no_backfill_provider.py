"""A minimal Provider with no BackfillProvider capability, for CLI tests only.

Both real Provider implementations (JmapProvider, FileProvider) now
implement query_messages() (docs/ROADMAP.md M8), so `spork backfill`'s
"provider doesn't support this" path has nothing real to exercise it
against — this exists purely so that edge case has a loadable
"module:Class" spec to point at.
"""

from __future__ import annotations

from spork.core.providers.base import (
    ActionApplier,
    DraftCreator,
    MailboxLister,
    MessageLookup,
    ThreadHistoryReader,
)
from spork.core.sources.base import Source
from spork.core.sources.replay import ImmediateTrigger, SequenceContentFetcher
from spork.core.sources.triggered import TriggeredSource


class NoBackfillProvider:
    """Satisfies `Provider` structurally; deliberately has no query_messages()."""

    def build_source(self) -> Source:
        return TriggeredSource(ImmediateTrigger(), SequenceContentFetcher([], batch_size=1))

    def build_action_applier(self) -> ActionApplier:
        raise NotImplementedError

    def build_draft_creator(self) -> DraftCreator:
        raise NotImplementedError

    def build_thread_history_reader(self) -> ThreadHistoryReader:
        raise NotImplementedError

    def build_mailbox_lister(self) -> MailboxLister:
        raise NotImplementedError

    def build_message_lookup(self) -> MessageLookup:
        raise NotImplementedError
