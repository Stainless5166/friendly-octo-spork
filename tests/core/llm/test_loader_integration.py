"""load_llm_client() against spork's real LLMClient implementations.

test_loader.py/test_loader_edge_cases.py prove the loader's own
import/instantiate/error-wrapping mechanics against a fixture
stand-in class — this file proves the two real implementations
actually resolve through it by the exact spec strings docs/DESIGN.md
§10.1/§10.5 document for config.toml's `[llm] client =`, not just that
they're importable directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spork.core.llm.base import VerdictRequest
from spork.core.llm.clients.anthropic import AnthropicLLMClient
from spork.core.llm.clients.recorded import RecordedLLMClient
from spork.core.llm.loader import load_llm_client


def test_load_llm_client_resolves_anthropic_llm_client_by_its_documented_spec() -> None:
    """The exact spec string §10.1 documents for config.toml resolves
    to a real AnthropicLLMClient, constructed with the given kwargs."""
    client = load_llm_client(
        "spork.core.llm.clients.anthropic:AnthropicLLMClient", api_key="fake-key"
    )

    assert isinstance(client, AnthropicLLMClient)


def test_load_llm_client_resolves_recorded_llm_client_by_its_documented_spec(
    tmp_path: Path,
) -> None:
    """The exact spec string §10.5 documents for config.toml resolves
    to a real RecordedLLMClient that genuinely works — loaded via the
    dynamic loader, not constructed directly."""
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(
        json.dumps(
            {
                "Test subject": {
                    "category": "fyi",
                    "urgency": "low",
                    "confidence": 0.9,
                    "suggested_action": {"type": "ignore"},
                    "summary": "s",
                    "reasoning": "r",
                }
            }
        )
    )

    client = load_llm_client(
        "spork.core.llm.clients.recorded:RecordedLLMClient", responses_path=str(responses_path)
    )

    assert isinstance(client, RecordedLLMClient)
    request = VerdictRequest(
        subject="Test subject",
        from_address="a@example.com",
        to_addresses=(),
        cleaned_body="body",
        thread_prior_subject=None,
        thread_user_has_replied=False,
        available_mailboxes=(),
    )
    assert client.get_verdict(request).category == "fyi"


def test_load_llm_client_propagates_anthropic_client_get_verdict_not_implemented() -> None:
    """A loaded AnthropicLLMClient still behaves like the real class —
    get_verdict() raises NotImplementedError, not something the loader
    itself would swallow or change."""
    client = load_llm_client(
        "spork.core.llm.clients.anthropic:AnthropicLLMClient", api_key="fake-key"
    )
    request = VerdictRequest(
        subject="s",
        from_address="a@example.com",
        to_addresses=(),
        cleaned_body="body",
        thread_prior_subject=None,
        thread_user_has_replied=False,
        available_mailboxes=(),
    )

    with pytest.raises(NotImplementedError):
        client.get_verdict(request)
