"""Acceptance tests for spork.core.context.base (docs/DESIGN.md §10.8).

ContextProvider is the generic, read-only "give me relevant background
for this message" seam the user asked for explicitly *not* as a
bespoke Obsidian integration — a Protocol any backend (a local
markdown vault, a full-text index, eventually a real Obsidian API)
structurally satisfies, mirroring ThreadHistoryReader/MailboxLister's
relationship to Provider.
"""

from __future__ import annotations

from spork.core.context.base import ContextProvider, ContextResult, ContextSnippet


def test_context_snippet_holds_a_source_and_text() -> None:
    snippet = ContextSnippet(source="notes/vendor-acme.md", text="ACME renews annually in March.")

    assert snippet.source == "notes/vendor-acme.md"
    assert snippet.text == "ACME renews annually in March."


def test_context_result_holds_zero_or_more_snippets() -> None:
    result = ContextResult(
        snippets=(
            ContextSnippet(source="a.md", text="A"),
            ContextSnippet(source="b.md", text="B"),
        )
    )

    assert len(result.snippets) == 2
    assert result.snippets[0].source == "a.md"


def test_context_result_empty_is_a_valid_no_context_answer() -> None:
    """ "No relevant context found" is a real, first-class answer — not
    an error, not a missing field."""
    result = ContextResult(snippets=())

    assert result.snippets == ()


def test_a_plain_class_with_get_context_structurally_satisfies_contextprovider(
    make_message,
) -> None:
    """Protocol-based DI, same as every other backend seam in this
    codebase (docs/DESIGN.md) — nothing needs to import or inherit
    from ContextProvider to satisfy it."""

    class _Fixture:
        def get_context(self, message: object) -> ContextResult:
            return ContextResult(snippets=())

    provider: ContextProvider = _Fixture()
    assert provider.get_context(make_message(message_id="msg-1")) == ContextResult(snippets=())
