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


class Provider(Protocol):
    """What every mail-backend integration (JMAP, IMAP, ...) adapts to.

    A provider is the daemon's *entire* relationship to one remote
    source of truth: reading from it (`build_source`) and writing to
    it (`build_action_applier`) are two operations against the same
    backend, not separate concerns that happen to share one
    implementation. Anything else backend-specific (mailbox role
    resolution) is reached through whatever a provider hands back, not
    through this Protocol — but read and write both belong here.
    """

    def build_source(self) -> Source: ...
    def build_action_applier(self) -> ActionApplier: ...
