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

from spork.core.llm.base import VerdictRequest
from spork.core.llm.clients.litellm import LiteLLMClient
from spork.core.llm.clients.recorded import RecordedLLMClient
from spork.core.llm.loader import load_llm_client


def test_load_llm_client_resolves_litellm_client_by_its_documented_spec() -> None:
    """The exact config spec resolves to a real LiteLLMClient."""
    client = load_llm_client(
        "spork.core.llm.clients.litellm:LiteLLMClient",
        model="anthropic/claude-sonnet-4-5",
        completion=lambda **_: None,
    )

    assert isinstance(client, LiteLLMClient)


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
        available_categories=(),
    )
    assert client.get_verdict(request).verdict.category == "fyi"
