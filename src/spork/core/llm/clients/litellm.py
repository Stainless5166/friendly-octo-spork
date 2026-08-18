"""In-process LiteLLM adapter using a forced structured verdict tool call (§10.1)."""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from spork.core.llm.base import LLMCallUsage, LLMResult, Verdict, VerdictRequest
from spork.core.llm.prompt import build_prompt

Completion = Callable[..., object]


class LiteLLMClientError(Exception):
    """Raised when LiteLLM is unavailable or its response cannot produce one Verdict."""


def _load_completion() -> Completion:
    """Import the optional SDK only when this live backend is constructed."""
    try:
        module = importlib.import_module("litellm")
    except ImportError as exc:
        raise LiteLLMClientError(
            "LiteLLMClient requires the optional LLM dependency; install spork[llm]"
        ) from exc
    completion: Completion = module.completion
    return completion


class LiteLLMClient:
    """Call any LiteLLM-supported model in-process and return one validated result."""

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        max_tokens: int = 1024,
        completion: Completion | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._api_base = api_base
        self._max_tokens = max_tokens
        self._completion = completion if completion is not None else _load_completion()

    def get_verdict(self, request: VerdictRequest) -> LLMResult:
        """Make one forced tool call and validate its arguments and usage."""
        prompt = build_prompt(request)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": list(prompt.messages),
            "tools": list(prompt.tools),
            "tool_choice": prompt.tool_choice,
        }
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        if self._api_base is not None:
            kwargs["api_base"] = self._api_base
        try:
            response = self._completion(**kwargs)
        except Exception as exc:
            raise LiteLLMClientError(f"LiteLLM completion failed: {exc}") from exc
        return _parse_response(response)


def _parse_response(response: object) -> LLMResult:
    """Translate LiteLLM's OpenAI-compatible response without leaking it downstream."""
    try:
        tool_calls = response.choices[0].message.tool_calls  # type: ignore[attr-defined]
        usage = response.usage  # type: ignore[attr-defined]
        if len(tool_calls) != 1:
            raise ValueError(f"expected exactly one tool call, got {len(tool_calls)}")
        function = tool_calls[0].function
        if function.name != "deliver_verdict":
            raise ValueError(f"unexpected tool call {function.name!r}")
        arguments = json.loads(function.arguments)
        verdict = Verdict.model_validate(arguments)
        tokens_in = int(usage.prompt_tokens)
        tokens_out = int(usage.completion_tokens)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, ValidationError) as exc:
        raise LiteLLMClientError(f"invalid LiteLLM verdict response: {exc}") from exc
    return LLMResult(
        verdict=verdict,
        usage=LLMCallUsage(tokens_in=tokens_in, tokens_out=tokens_out),
    )
