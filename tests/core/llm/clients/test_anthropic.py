"""Spec tests for AnthropicLLMClient (docs/ROADMAP.md M3), catching its
deliberate NotImplementedError placeholder.

get_verdict() requires a real Anthropic API session — not something a
unit test (or this environment) can exercise honestly. Rather than
leaving the class unspecified until that's possible, this locks in its
shape (constructor args, method name/signature) now, and asserts it
raises a clear, catchable NotImplementedError rather than doing
nothing or silently pretending to work. Mirrors
tests/core/providers/jmap/test_client.py's JmapClient tests exactly.
This is an ordinary passing test, not xfail — "not implemented" is the
correct, specified behavior at this stage.
"""

from __future__ import annotations

import pytest

from spork.core.llm.base import VerdictRequest
from spork.core.llm.clients.anthropic import AnthropicLLMClient


def _request() -> VerdictRequest:
    return VerdictRequest(
        subject="Test subject",
        from_address="someone@example.com",
        to_addresses=("me@example.com",),
        cleaned_body="Cleaned test body.",
        thread_prior_subject=None,
        thread_user_has_replied=False,
        available_mailboxes=("Inbox", "Needs-Reply"),
    )


def test_get_verdict_raises_not_implemented() -> None:
    """get_verdict() would call the live Anthropic API — not built yet."""
    client = AnthropicLLMClient(api_key="fake-key")

    with pytest.raises(NotImplementedError):
        client.get_verdict(_request())


def test_constructor_accepts_configured_model_and_max_tokens() -> None:
    """model/max_tokens are settled constructor args (docs/DESIGN.md
    §10) even though nothing consumes them yet — constructing with
    non-default values doesn't raise."""
    client = AnthropicLLMClient(api_key="fake-key", model="claude-opus-5", max_tokens=2048)

    with pytest.raises(NotImplementedError):
        client.get_verdict(_request())
