"""Failure and append-semantics tests for the private acceptance corpus recorder."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from spork.core.llm.base import LLMCallUsage, LLMResult, Verdict, VerdictRequest
from spork.core.llm.prompt import build_prompt
from spork.core.llm.recording import RecordingLLMClient, prompt_sha256


def _request(subject: str, body: str = "Body") -> VerdictRequest:
    return VerdictRequest(
        subject=subject,
        from_address="sender@example.com",
        to_addresses=(),
        cleaned_body=body,
        thread_prior_subject=None,
        thread_user_has_replied=False,
        available_mailboxes=("Inbox",),
        available_categories=(),
        context_snippets=(),
    )


def _result() -> LLMResult:
    return LLMResult(
        verdict=Verdict.model_validate(
            {
                "category": "fyi",
                "urgency": "low",
                "confidence": 0.9,
                "suggested_action": {"type": "ignore"},
                "summary": "For information.",
                "reasoning": "No action requested.",
            }
        ),
        usage=LLMCallUsage(tokens_in=10, tokens_out=5),
    )


def test_failed_call_is_never_recorded(tmp_path: Path) -> None:
    class FailingClient:
        def get_verdict(self, request: VerdictRequest) -> LLMResult:
            raise RuntimeError("upstream failed")

    corpus_path = tmp_path / "corpus" / "live.jsonl"
    client = RecordingLLMClient(FailingClient(), corpus_path=corpus_path)

    with pytest.raises(RuntimeError, match="upstream failed"):
        client.get_verdict(_request("Failure"))

    assert not corpus_path.exists()


def test_successful_calls_append_independent_json_lines(tmp_path: Path) -> None:
    class StubClient:
        def get_verdict(self, request: VerdictRequest) -> LLMResult:
            return _result()

    corpus_path = tmp_path / "live.jsonl"
    client = RecordingLLMClient(StubClient(), corpus_path=corpus_path, now=lambda: "fixed")

    client.get_verdict(_request("First"))
    client.get_verdict(_request("Second"))

    entries = [json.loads(line) for line in corpus_path.read_text().splitlines()]
    assert [entry["subject"] for entry in entries] == ["First", "Second"]
    assert entries[0]["prompt_sha256"] != entries[1]["prompt_sha256"]


def test_prompt_hash_is_stable_but_sensitive_to_message_content() -> None:
    first = build_prompt(_request("Same", body="First body"))
    same = build_prompt(_request("Same", body="First body"))
    changed = build_prompt(_request("Same", body="Second body"))

    assert prompt_sha256(first) == prompt_sha256(same)
    assert prompt_sha256(first) != prompt_sha256(changed)


def test_default_recording_clock_writes_a_parseable_utc_timestamp(tmp_path: Path) -> None:
    class StubClient:
        def get_verdict(self, request: VerdictRequest) -> LLMResult:
            return _result()

    corpus_path = tmp_path / "live.jsonl"

    RecordingLLMClient(StubClient(), corpus_path=corpus_path).get_verdict(_request("Timed"))

    recorded_at = json.loads(corpus_path.read_text())["recorded_at"]
    timestamp = datetime.fromisoformat(recorded_at)
    assert timestamp.utcoffset() is not None
