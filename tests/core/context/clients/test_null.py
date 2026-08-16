"""Acceptance tests for NullContextProvider (docs/DESIGN.md §10.8).

The real, fully-working default when `[context]` is omitted from
config.toml entirely — "no knowledgebase configured" is a legitimate
state, same relationship `local_classifier: None` has to the classify
registry, not a stand-in for a backend that doesn't exist yet.
"""

from __future__ import annotations

from spork.core.context.base import ContextResult
from spork.core.context.clients.null import NullContextProvider


def test_null_context_provider_always_returns_an_empty_result(make_message) -> None:
    provider = NullContextProvider()

    result = provider.get_context(make_message(message_id="msg-1", subject="Anything at all"))

    assert result == ContextResult(snippets=())


def test_null_context_provider_takes_no_constructor_arguments() -> None:
    """No config, no kwargs to get wrong — this is the safe default a
    minimal config.toml (no [context] table) resolves to."""
    provider = NullContextProvider()

    assert isinstance(provider, NullContextProvider)
