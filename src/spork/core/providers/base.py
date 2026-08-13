"""The common contract every mail-backend provider adapts to (§9.3)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from spork.core.models import NormalizedMessage
from spork.core.rules.schema import Action
from spork.core.sources.base import Source


class ActionApplier(Protocol):
    """Applies one rule/verdict Action to a message on the remote backend.

    A provider's write side. Not a separate DI concern from `Source`
    (the read side) — see `Provider`'s docstring for why both belong
    to the same contract.
    """

    def apply(self, message: NormalizedMessage, action: Action) -> None: ...


class DraftCreator(Protocol):
    """Creates a draft reply in the account's Drafts mailbox.

    A provider's second write side, alongside `ActionApplier` — the
    M3 counterpart for `Verdict.draft_reply` (docs/DESIGN.md §10.1,
    §10.6). Never sent: no `Provider`/`DraftCreator` implementation
    anywhere in this codebase has a path to `EmailSubmission/set` —
    §11's "draft, never send" invariant is enforced by omission.
    """

    def create_draft(self, in_reply_to: NormalizedMessage, body: str) -> None: ...


@dataclass(frozen=True, slots=True)
class ThreadContext:
    """Everything `process_tier2_message()`'s `Tier2Meta` needs about a
    message's thread history (docs/DESIGN.md §9.3, §10.7).

    Deliberately narrow — exactly the two facts Tier 2 consults
    (`thread_prior_subject`, `thread_user_has_replied`), not a
    general-purpose thread-search result.
    """

    prior_subject: str | None
    user_has_replied: bool


class ThreadHistoryReader(Protocol):
    """Resolves one message's `ThreadContext` — a provider's third read
    side, alongside `Source` (new mail) and whatever `build_action_applier()`
    reads to apply an action.
    """

    def get_thread_context(self, message: NormalizedMessage) -> ThreadContext: ...


class MailboxLister(Protocol):
    """Lists the account's mailbox names, for Tier 2's `available_mailboxes`
    (§10.1) and `validate_verdict()`'s closed-set check (§10.2).
    """

    def list_mailboxes(self) -> Sequence[str]: ...


class Provider(Protocol):
    """What every mail-backend integration (JMAP, IMAP, ...) adapts to.

    A provider is the daemon's *entire* relationship to one remote
    source of truth: reading from it (`build_source`), writing an
    action to it (`build_action_applier`), writing a draft to it
    (`build_draft_creator`), and answering the two read-side questions
    Tier 2 needs (`build_thread_history_reader`, `build_mailbox_lister`)
    are five operations against the same backend, not separate concerns
    that happen to share one implementation. Anything else
    backend-specific (mailbox role resolution) is reached through
    whatever a provider hands back, not through this Protocol — but
    every kind of read/write belongs here.
    """

    def build_source(self) -> Source: ...
    def build_action_applier(self) -> ActionApplier: ...
    def build_draft_creator(self) -> DraftCreator: ...
    def build_thread_history_reader(self) -> ThreadHistoryReader: ...
    def build_mailbox_lister(self) -> MailboxLister: ...
