"""Tests for the standalone Ollama benchmark's structured-output boundary."""

from __future__ import annotations

import pytest

from spork.core.classify.decisions import Classification
from spork.core.llm.ollama_benchmark import (
    build_benchmark_record,
    email_fingerprint,
    parse_classifications,
    split_known_candidates,
)


def test_parse_classifications_accepts_json_and_merges_duplicate_names() -> None:
    result = parse_classifications(
        '{"classifications":[{"name":"banking","score":80},'
        '{"name":"banking","score":100},{"name":"alert","score":70}]}'
    )

    assert result == (
        Classification(name="alert", score=70),
        Classification(name="banking", score=100),
    )


def test_parse_classifications_accepts_a_fenced_json_response() -> None:
    result = parse_classifications('```json\n{"classifications": []}\n```')

    assert result == ()


@pytest.mark.parametrize("payload", ["not json", '{"wrong": []}', '{"classifications": "bad"}'])
def test_parse_classifications_rejects_invalid_model_output(payload: str) -> None:
    with pytest.raises(ValueError):
        parse_classifications(payload)


def test_build_benchmark_record_does_not_include_message_content() -> None:
    record = build_benchmark_record(
        model="provider/test-model",
        message_id="message-1",
        subject="Private subject",
        classifications=(Classification(name="banking", score=100),),
        latency_ms=12.5,
        tokens_in=10,
        tokens_out=4,
        error=None,
        ps_before={"models": []},
        ps_after={"models": []},
        known_categories=frozenset({"banking"}),
        fingerprint="fingerprint-1",
    )

    assert record["message_id"] == "message-1"
    assert "Private subject" not in str(record)
    assert "body_text" not in record
    assert record["classifications"] == [{"name": "banking", "score": 100.0, "status": "known"}]


def test_split_known_candidates_keeps_novel_labels_for_review_only() -> None:
    known, candidates = split_known_candidates(
        (Classification(name="banking", score=100), Classification(name="phishing", score=90)),
        frozenset({"banking"}),
    )

    assert known == (Classification(name="banking", score=100),)
    assert candidates == (Classification(name="phishing", score=90),)


def test_email_fingerprint_ignores_case_and_whitespace_formatting() -> None:
    first = email_fingerprint("alerts@example.com", "Weekly report", "Total: 10\nItems: 2")
    second = email_fingerprint("ALERTS@EXAMPLE.COM", " weekly   report ", "Total: 10 Items: 2")

    assert first == second
