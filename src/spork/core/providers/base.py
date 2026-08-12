"""The common contract every mail-backend provider adapts to (§9.3)."""

from __future__ import annotations

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


class Provider(Protocol):
    """What every mail-backend integration (JMAP, IMAP, ...) adapts to.

    A provider is the daemon's *entire* relationship to one remote
    source of truth: reading from it (`build_source`), writing an
    action to it (`build_action_applier`), and writing a draft to it
    (`build_draft_creator`) are three operations against the same
    backend, not separate concerns that happen to share one
    implementation. Anything else backend-specific (mailbox role
    resolution) is reached through whatever a provider hands back, not
    through this Protocol — but every kind of read/write belongs here.
    """

    def build_source(self) -> Source: ...
    def build_action_applier(self) -> ActionApplier: ...
    def build_draft_creator(self) -> DraftCreator: ...
