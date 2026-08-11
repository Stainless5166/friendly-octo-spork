"""The common contract every mail-backend provider adapts to (§9.3)."""

from __future__ import annotations

from typing import Protocol

from spork.core.sources.base import Source


class Provider(Protocol):
    """What every mail-backend integration (JMAP, IMAP, ...) adapts to.

    Deliberately the smallest useful contract: the daemon's ingestion
    loop only ever needs "give me a Source" — it doesn't care whether
    that Source is backed by JMAP push, IMAP polling, or a replay
    fixture. Capabilities specific to one backend (mailbox role
    resolution, an action executor's mutation calls) are the
    provider's own concern, reached through whatever it hands back,
    not through this Protocol.
    """

    def build_source(self) -> Source: ...
