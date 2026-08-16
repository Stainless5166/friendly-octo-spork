"""NullContextProvider: the real "no knowledgebase configured" backend (docs/DESIGN.md §10.8).

Not a stand-in for a backend that doesn't exist yet — "nothing
configured" is a legitimate deployment state, same relationship
`TieringConfig.local_classifier: None` has to the classify registry.
This is what `spork.core.runtime.build_context_provider()` returns
when `SporkConfig.context` is `None` (no `[context]` table).
"""

from __future__ import annotations

from spork.core.context.base import ContextResult
from spork.core.models import NormalizedMessage


class NullContextProvider:
    """Always answers "no relevant context" — zero configuration, zero I/O."""

    def get_context(self, message: NormalizedMessage) -> ContextResult:
        return ContextResult(snippets=())
