"""Acceptance tests for LiteLLMClient using a mocked upstream completion call."""

from __future__ import annotations

import json
from types import SimpleNamespace

from spork.core.llm.base import LLMResult, VerdictRequest
from spork.core.llm.clients.litellm import LiteLLMClient
from spork.core.llm.prompt import build_prompt


def _request() -> VerdictRequest:
    return VerdictRequest(
        subject="Test subject",
        from_address="sender@example.com",
        to_addresses=("me@example.com",),
        cleaned_body="Please reply.",
        thread_prior_subject=None,
        thread_user_has_replied=False,
        available_mailboxes=("Inbox", "Needs-Reply"),
        available_categories=(),
        context_snippets=(),
    )


def _response() -> SimpleNamespace:
    arguments = json.dumps(
        {
            "category": "needs_reply",
            "urgency": "high",
            "confidence": 0.91,
            "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
            "summary": "A response is requested.",
            "reasoning": "The sender asks directly for a reply.",
        }
    )
    function = SimpleNamespace(name="deliver_verdict", arguments=arguments)
    tool_call = SimpleNamespace(function=function)
    message = SimpleNamespace(tool_calls=[tool_call])
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=123, completion_tokens=45),
    )


def test_litellm_client_sends_the_exact_prompt_and_forced_tool_choice() -> None:
    calls: list[dict[str, object]] = []

    def completion(**kwargs: object) -> object:
        calls.append(kwargs)
        return _response()

    request = _request()
    client = LiteLLMClient(
        model="anthropic/claude-sonnet-4-5",
        api_key="test-key",
        api_base="http://llm.example.test:11434",
        max_tokens=2048,
        completion=completion,
    )

    client.get_verdict(request)

    prompt = build_prompt(request)
    assert calls == [
        {
            "model": "anthropic/claude-sonnet-4-5",
            "api_key": "test-key",
            "api_base": "http://llm.example.test:11434",
            "max_tokens": 2048,
            "messages": list(prompt.messages),
            "tools": list(prompt.tools),
            "tool_choice": prompt.tool_choice,
        }
    ]


def test_litellm_client_parses_the_tool_arguments_and_real_token_usage() -> None:
    client = LiteLLMClient(model="anthropic/claude-sonnet-4-5", completion=lambda **_: _response())

    result = client.get_verdict(_request())

    assert isinstance(result, LLMResult)
    assert result.verdict.category == "needs_reply"
    assert result.verdict.suggested_action.mailbox == "Needs-Reply"
    assert result.usage.tokens_in == 123
    assert result.usage.tokens_out == 45
