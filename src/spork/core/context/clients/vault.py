"""MarkdownVaultContextProvider: a settled-shape stub (docs/DESIGN.md §10.8, docs/ROADMAP.md M9).

Real constructor argument settled now (`vault_path`), same "settle
the shape for real, raise until the behavior is built" split
`JmapClient` uses — but for a different reason than a live-network
blocker: which retrieval algorithm to use (plain substring/keyword
match vs. something ranked) isn't a decided design question yet, and
this environment has no real vault content to validate either choice
against honestly. `NullContextProvider` (§10.8) is the real, working
default in the meantime — this class exists so the eventual real
backend has a settled home to land in, not to fake retrieval today.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.context.base import ContextResult
from spork.core.models import NormalizedMessage


class MarkdownVaultContextProvider:
    """Reads relevant snippets from a local directory of markdown notes.

    Construction never touches the filesystem — `vault_path` doesn't
    need to exist yet to build one — so this can be wired into a
    config file well before the retrieval logic is decided.
    """

    def __init__(self, vault_path: str | Path) -> None:
        self.vault_path = Path(vault_path)

    def get_context(self, message: NormalizedMessage) -> ContextResult:
        raise NotImplementedError(
            "MarkdownVaultContextProvider.get_context() is a settled-shape stub — "
            "the real retrieval algorithm (keyword vs. ranked search over vault "
            "content) is undecided design work, see docs/ROADMAP.md M9. Configure "
            "spork.core.context.clients.null:NullContextProvider (the default when "
            "[context] is omitted) until this lands."
        )
