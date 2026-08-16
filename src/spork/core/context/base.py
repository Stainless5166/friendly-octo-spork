"""ContextProvider: the read-only knowledgebase adapter contract (docs/DESIGN.md §10.8).

Deliberately generic — the user asked explicitly for "a read right
context/knowledgebase interface", not a bespoke Obsidian config. A
`Protocol`, not an ABC, same as `LLMClient`/`Provider`/`Alerter`:
nothing needs to import or inherit from anything here to satisfy it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from spork.core.models import NormalizedMessage


@dataclass(frozen=True, slots=True)
class ContextSnippet:
    """One piece of retrieved background — a title/path (`source`) plus
    the text itself, kept separate so a caller can cite where a
    snippet came from without parsing it back out of free text."""

    source: str
    text: str


@dataclass(frozen=True, slots=True)
class ContextResult:
    """Zero or more `ContextSnippet`s relevant to one message.

    Empty is a real, first-class answer ("no relevant context found"),
    not an error and not a missing field — `NullContextProvider`
    (the default when `[context]` is unconfigured) always returns one.
    """

    snippets: tuple[ContextSnippet, ...]


class ContextProvider(Protocol):
    """What every read-only knowledgebase backend adapts to.

    Takes the whole `NormalizedMessage`, not a narrower query type —
    same shape `ThreadHistoryReader.get_thread_context()` uses
    (`spork.core.providers.base`) — so a real backend can look at
    whatever fields it needs (subject, sender, body) without this
    Protocol having to anticipate which ones in advance.
    """

    def get_context(self, message: NormalizedMessage) -> ContextResult: ...
