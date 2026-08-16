"""Failure/edge-case tests for RecordedLLMClient and load_recorded_responses.

Companion to test_recorded.py/test_recorded_responses.py's acceptance
tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spork.core.llm.base import VerdictRequest
from spork.core.llm.clients.recorded import (
    RecordedLLMClient,
    RecordedResponsesLoadError,
    load_recorded_responses,
)


def _request(subject: str) -> VerdictRequest:
    return VerdictRequest(
        subject=subject,
        from_address="someone@example.com",
        to_addresses=("me@example.com",),
        cleaned_body="Cleaned test body.",
        thread_prior_subject=None,
        thread_user_has_replied=False,
        available_mailboxes=("Inbox",),
        available_categories=(),
    )


def test_load_recorded_responses_fails_entirely_when_any_entry_is_invalid(
    tmp_path: Path,
) -> None:
    """A file with one valid entry and one invalid entry raises for the
    whole file — no partial load that silently drops the bad entry and
    returns the rest, which would make a CI fixture's coverage quietly
    incomplete instead of loudly broken."""
    path = tmp_path / "responses.json"
    path.write_text(
        json.dumps(
            {
                "Good entry": {
                    "category": "fyi",
                    "urgency": "low",
                    "confidence": 0.9,
                    "suggested_action": {"type": "ignore"},
                    "summary": "s",
                    "reasoning": "r",
                },
                "Bad entry": {"category": "fyi"},
            }
        )
    )

    with pytest.raises(RecordedResponsesLoadError):
        load_recorded_responses(path)


def test_duplicate_subject_keys_in_the_json_keep_only_the_last(tmp_path: Path) -> None:
    """EDGE CASE FOUND WHILE TESTING: JSON syntax allows a duplicate
    key in an object; Python's json.loads silently keeps only the
    last occurrence (this is stdlib json's behavior, not anything
    spork does) — so a fixture file with a copy-pasted-then-edited
    subject line loses the first entry with no error at all. Not
    fixed here (would need a custom object_pairs_hook to detect it,
    more machinery than a CI-fixture loader needs); documented so a
    future reader debugging "why did my fixture only have N-1
    responses" finds the answer here, not by rediscovering it."""
    path = tmp_path / "responses.json"
    path.write_text(
        '{"Same subject": {"category": "first", "urgency": "low", "confidence": 0.5, '
        '"suggested_action": {"type": "ignore"}, "summary": "s1", "reasoning": "r1"}, '
        '"Same subject": {"category": "second", "urgency": "low", "confidence": 0.5, '
        '"suggested_action": {"type": "ignore"}, "summary": "s2", "reasoning": "r2"}}'
    )

    responses = load_recorded_responses(path)

    assert len(responses) == 1
    assert responses["Same subject"].category == "second"


def test_a_directory_path_raises_an_unwrapped_os_error(tmp_path: Path) -> None:
    """KNOWN GAP, matched to spork.core.providers.file.messages.load_messages()'s
    identical limitation: passing a directory instead of a file leaks
    Path.read_text()'s raw IsADirectoryError rather than a clear
    RecordedResponsesLoadError, since only FileNotFoundError/
    JSONDecodeError are caught. Documented rather than fixed here, to
    keep this loader's error handling an intentional mirror of its
    sibling rather than silently diverging from it."""
    with pytest.raises(IsADirectoryError):
        load_recorded_responses(tmp_path)


def test_get_verdict_can_be_called_more_than_once_for_the_same_subject(
    tmp_path: Path,
) -> None:
    """Recorded responses aren't a single-use queue — requesting the
    same subject twice returns the same recorded Verdict both times,
    the way a real API call for the same input would be expected to
    behave consistently across retries in a test."""
    path = tmp_path / "responses.json"
    path.write_text(
        json.dumps(
            {
                "Repeatable": {
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
    client = RecordedLLMClient(path)

    first = client.get_verdict(_request("Repeatable"))
    second = client.get_verdict(_request("Repeatable"))

    assert first == second
