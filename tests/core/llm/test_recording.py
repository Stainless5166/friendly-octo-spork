"""Acceptance tests for recording exact live prompts and results to a private corpus."""

from __future__ import annotations

import json
from pathlib import Path

from spork.core.llm.base import LLMCallUsage, LLMResult, Verdict, VerdictRequest
from spork.core.llm.prompt import build_prompt
from spork.core.llm.recording import RecordingLLMClient, prompt_sha256


def _request() -> VerdictRequest:
    return VerdictRequest(
        subject="Private subject",
        from_address="sender@example.com",
        to_addresses=("me@example.com",),
        cleaned_body="Private body.",
        thread_prior_subject=None,
        thread_user_has_replied=False,
        available_mailboxes=("Inbox",),
        available_categories=(),
    )


class _StubClient:
    def get_verdict(self, request: VerdictRequest) -> LLMResult:
        return LLMResult(
            verdict=Verdict.model_validate(
                {
                    "category": "fyi",
                    "urgency": "low",
                    "confidence": 0.9,
                    "suggested_action": {"type": "ignore"},
                    "summary": "For information.",
                    "reasoning": "No response requested.",
                }
            ),
            usage=LLMCallUsage(tokens_in=37, tokens_out=19),
        )


def test_recording_client_appends_the_complete_prompt_result_and_usage(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus" / "live.jsonl"
    request = _request()
    client = RecordingLLMClient(
        _StubClient(), corpus_path=corpus_path, now=lambda: "2026-08-14T10:00:00+00:00"
    )

    result = client.get_verdict(request)

    entry = json.loads(corpus_path.read_text())
    prompt = build_prompt(request)
    assert entry["subject"] == "Private subject"
    assert entry["prompt"] == {
        "messages": list(prompt.messages),
        "tools": list(prompt.tools),
        "tool_choice": prompt.tool_choice,
    }
    assert entry["prompt_sha256"] == prompt_sha256(prompt)
    assert entry["verdict"] == result.verdict.model_dump(mode="json")
    assert entry["usage"] == {"tokens_in": 37, "tokens_out": 19}
    assert entry["recorded_at"] == "2026-08-14T10:00:00+00:00"


def test_live_acceptance_corpus_directory_is_gitignored() -> None:
    root = Path(__file__).parents[3]

    assert "/tests/fixtures/corpus/" in (root / ".gitignore").read_text().splitlines()
