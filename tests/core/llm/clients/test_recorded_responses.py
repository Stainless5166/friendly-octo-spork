"""Acceptance tests for the recorded-responses loader (docs/DESIGN.md §10.5).

Mirrors spork.core.providers.file.messages's test shape: parsing,
empty-input, and wrapping every failure mode as one clear, catchable
error type instead of letting json/pydantic errors leak through
unwrapped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spork.core.llm.base import Verdict
from spork.core.llm.clients.recorded import RecordedResponsesLoadError, load_recorded_responses


def test_load_recorded_responses_parses_a_valid_json_file(tmp_path: Path) -> None:
    """A well-formed responses.json parses into Verdicts, keyed by
    subject."""
    path = tmp_path / "responses.json"
    path.write_text(
        json.dumps(
            {
                "Re: Thursday call": {
                    "category": "needs_reply",
                    "urgency": "high",
                    "confidence": 0.78,
                    "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
                    "summary": "Move Thursday's call to Friday 2pm.",
                    "reasoning": "Direct scheduling question.",
                }
            }
        )
    )

    responses = load_recorded_responses(path)

    assert set(responses) == {"Re: Thursday call"}
    assert isinstance(responses["Re: Thursday call"], Verdict)
    assert responses["Re: Thursday call"].category == "needs_reply"


def test_load_recorded_responses_returns_empty_dict_for_empty_object(tmp_path: Path) -> None:
    """A syntactically valid file containing `{}` is zero recorded
    responses, not an error — an empty fixture is a legitimate
    starting point."""
    path = tmp_path / "responses.json"
    path.write_text("{}")

    assert load_recorded_responses(path) == {}


def test_load_recorded_responses_raises_for_malformed_json(tmp_path: Path) -> None:
    """Broken JSON syntax is a clear RecordedResponsesLoadError, not a
    raw json.JSONDecodeError leaking through unwrapped."""
    path = tmp_path / "responses.json"
    path.write_text("this is not { valid json")

    with pytest.raises(RecordedResponsesLoadError):
        load_recorded_responses(path)


def test_load_recorded_responses_raises_for_non_object_json(tmp_path: Path) -> None:
    """A file whose top level isn't a JSON object (e.g. an array) is a
    clear RecordedResponsesLoadError, not an unhelpful error further
    down."""
    path = tmp_path / "responses.json"
    path.write_text(json.dumps([{"category": "fyi"}]))

    with pytest.raises(RecordedResponsesLoadError):
        load_recorded_responses(path)


def test_load_recorded_responses_raises_for_an_invalid_verdict_entry(tmp_path: Path) -> None:
    """An entry that fails Verdict's own validation (here, a missing
    required field) is a clear RecordedResponsesLoadError naming the
    subject, not a raw pydantic ValidationError leaking through
    unwrapped."""
    path = tmp_path / "responses.json"
    path.write_text(json.dumps({"Bad entry": {"category": "fyi"}}))

    with pytest.raises(RecordedResponsesLoadError, match="Bad entry"):
        load_recorded_responses(path)


def test_load_recorded_responses_raises_for_missing_file(tmp_path: Path) -> None:
    """A path that doesn't exist is a clear RecordedResponsesLoadError,
    not a raw FileNotFoundError."""
    with pytest.raises(RecordedResponsesLoadError):
        load_recorded_responses(tmp_path / "does-not-exist.json")
