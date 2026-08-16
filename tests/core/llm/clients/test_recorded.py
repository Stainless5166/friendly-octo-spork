"""Acceptance tests for RecordedLLMClient (docs/DESIGN.md §10.5).

The LLMClient equivalent of FileProvider (§9.3): a second, fully real
adapter with no NotImplementedError anywhere — these tests confirm the
LLMClient abstraction actually holds for a backend other than
AnthropicLLMClient, and that get_verdict() genuinely replays recorded
data rather than being a placeholder.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spork.core.llm.base import Verdict, VerdictRequest
from spork.core.llm.clients.recorded import RecordedLLMClient, UnrecordedResponseError


def _request(subject: str = "Re: Thursday call") -> VerdictRequest:
    return VerdictRequest(
        subject=subject,
        from_address="someone@example.com",
        to_addresses=("me@example.com",),
        cleaned_body="Cleaned test body.",
        thread_prior_subject=None,
        thread_user_has_replied=False,
        available_mailboxes=("Inbox", "Needs-Reply"),
        available_categories=(),
        context_snippets=(),
    )


def _write_responses(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "Re: Thursday call": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.78,
                    "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
                    "summary": "Client wants to move Thursday's call to Friday 2pm.",
                    "reasoning": "Sender asked a direct scheduling question.",
                },
                "Newsletter": {
                    "category": "fyi",
                    "urgency": "low",
                    "confidence": 0.95,
                    "suggested_action": {"type": "ignore"},
                    "summary": "Routine newsletter.",
                    "reasoning": "No action requested.",
                },
            }
        )
    )


def test_get_verdict_returns_the_recorded_verdict_for_a_matching_subject(
    tmp_path: Path,
) -> None:
    """A request whose subject matches a recorded entry gets that
    entry back, parsed into a real Verdict."""
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path)
    client = RecordedLLMClient(responses_path)

    result = client.get_verdict(_request("Re: Thursday call"))

    assert isinstance(result.verdict, Verdict)
    assert result.verdict.category == "needs_reply"
    assert result.verdict.suggested_action.mailbox == "Needs-Reply"
    assert result.usage.tokens_in == 0
    assert result.usage.tokens_out == 0


def test_get_verdict_returns_different_verdicts_for_different_subjects(
    tmp_path: Path,
) -> None:
    """Two different recorded subjects return their own distinct
    verdicts — proving this isn't just always returning one fixed
    response."""
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path)
    client = RecordedLLMClient(responses_path)

    first = client.get_verdict(_request("Re: Thursday call"))
    second = client.get_verdict(_request("Newsletter"))

    assert first.verdict.category == "needs_reply"
    assert second.verdict.category == "fyi"


def test_get_verdict_raises_for_a_subject_with_no_recorded_response(tmp_path: Path) -> None:
    """A request whose subject was never recorded fails loudly, naming
    what *was* recorded — same "name what's available" shape as
    UnknownBranchError (§9.4)."""
    responses_path = tmp_path / "responses.json"
    _write_responses(responses_path)
    client = RecordedLLMClient(responses_path)

    with pytest.raises(UnrecordedResponseError, match="Re: Thursday call"):
        client.get_verdict(_request("An email nobody recorded"))
