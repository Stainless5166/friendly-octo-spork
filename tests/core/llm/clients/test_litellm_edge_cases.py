"""Failure and edge-case tests for the in-process LiteLLM adapter."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from spork.core.llm.base import VerdictRequest
from spork.core.llm.clients.litellm import LiteLLMClient, LiteLLMClientError


def _request() -> VerdictRequest:
    return VerdictRequest(
        subject="Subject",
        from_address="sender@example.com",
        to_addresses=(),
        cleaned_body="Body",
        thread_prior_subject=None,
        thread_user_has_replied=False,
        available_mailboxes=("Inbox",),
        available_categories=(),
    )


def _arguments() -> str:
    return json.dumps(
        {
            "category": "fyi",
            "urgency": "low",
            "confidence": 0.9,
            "suggested_action": {"type": "ignore"},
            "summary": "For information.",
            "reasoning": "No action requested.",
        }
    )


def _response(*, tool_calls: object, usage: object | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=tool_calls))],
        usage=usage or SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def _tool_call(*, name: str = "deliver_verdict", arguments: str | None = None) -> object:
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments or _arguments()))


def test_constructor_reports_how_to_install_the_missing_optional_dependency(monkeypatch) -> None:
    def missing_module(name: str) -> object:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("spork.core.llm.clients.litellm.importlib.import_module", missing_module)

    with pytest.raises(LiteLLMClientError, match=r"spork\[llm\]"):
        LiteLLMClient(model="anthropic/test")


def test_constructor_loads_the_optional_sdk_completion_when_not_injected(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def completion(**kwargs: object) -> object:
        calls.append(kwargs)
        return _response(tool_calls=[_tool_call()])

    monkeypatch.setattr(
        "spork.core.llm.clients.litellm.importlib.import_module",
        lambda name: SimpleNamespace(completion=completion),
    )

    client = LiteLLMClient(model="anthropic/test")
    client.get_verdict(_request())

    assert len(calls) == 1


def test_upstream_completion_failure_is_wrapped_at_the_client_boundary() -> None:
    def completion(**kwargs: object) -> object:
        raise TimeoutError("provider timed out")

    client = LiteLLMClient(model="anthropic/test", completion=completion)

    with pytest.raises(LiteLLMClientError, match="provider timed out") as caught:
        client.get_verdict(_request())

    assert isinstance(caught.value.__cause__, TimeoutError)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (_response(tool_calls=[]), "exactly one tool call"),
        (_response(tool_calls=[_tool_call(), _tool_call()]), "exactly one tool call"),
        (_response(tool_calls=[_tool_call(name="other_tool")]), "unexpected tool call"),
        (_response(tool_calls=[_tool_call(arguments="not-json")]), "invalid LiteLLM"),
        (
            _response(tool_calls=[_tool_call(arguments=json.dumps({"category": "fyi"}))]),
            "invalid LiteLLM",
        ),
        (_response(tool_calls=[_tool_call()], usage=SimpleNamespace()), "invalid LiteLLM"),
    ],
)
def test_malformed_tool_responses_fail_closed(response: object, message: str) -> None:
    client = LiteLLMClient(model="anthropic/test", completion=lambda **_: response)

    with pytest.raises(LiteLLMClientError, match=message):
        client.get_verdict(_request())
