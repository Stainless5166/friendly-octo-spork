"""Acceptance tests for spork.core.llm.base (docs/DESIGN.md §10.1).

VerdictRequest is a plain frozen dataclass (spork's own assembled
input, never untrusted); Verdict is a pydantic model since it's the
one place spork parses untrusted external structured output (an LLM's
response) — same reasoning as rules.schema validating rules.toml.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from spork.core.llm.base import Verdict, VerdictRequest
from spork.core.rules.schema import Action


def _request(**overrides: object) -> VerdictRequest:
    defaults: dict[str, object] = {
        "subject": "Test subject",
        "from_address": "someone@example.com",
        "to_addresses": ("me@example.com",),
        "cleaned_body": "Cleaned test body.",
        "thread_prior_subject": None,
        "thread_user_has_replied": False,
        "available_mailboxes": ("Inbox", "Needs-Reply"),
        "available_categories": ("needs_reply", "fyi"),
    }
    defaults.update(overrides)
    return VerdictRequest(**defaults)  # type: ignore[arg-type]


def _verdict_json(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "category": "needs_reply",
        "urgency": "high",
        "confidence": 0.78,
        "suggested_action": {"type": "tag", "mailbox": "Needs-Reply"},
        "summary": "Client wants to move Thursday's call to Friday 2pm.",
        "reasoning": "Sender asked a direct scheduling question.",
    }
    defaults.update(overrides)
    return defaults


def test_verdict_request_holds_the_assembled_prompt_inputs() -> None:
    """A VerdictRequest carries exactly the fields §10 lists as LLM
    input — constructing one and reading each field back works."""
    request = _request(subject="Re: Thursday call", thread_user_has_replied=True)

    assert request.subject == "Re: Thursday call"
    assert request.thread_user_has_replied is True
    assert request.available_mailboxes == ("Inbox", "Needs-Reply")
    assert request.available_categories == ("needs_reply", "fyi")


def test_verdict_parses_a_valid_llm_response() -> None:
    """A well-formed response dict (matching §10's JSON example)
    parses into a Verdict with a nested Action."""
    verdict = Verdict.model_validate(_verdict_json())

    assert verdict.category == "needs_reply"
    assert verdict.urgency == "high"
    assert isinstance(verdict.suggested_action, Action)
    assert verdict.suggested_action.type == "tag"
    assert verdict.suggested_action.mailbox == "Needs-Reply"


def test_verdict_draft_reply_defaults_to_none_when_omitted() -> None:
    """draft_reply is optional per §10 (only populated for categories
    configured to want one) — omitting it from the response is valid."""
    verdict = Verdict.model_validate(_verdict_json())

    assert verdict.draft_reply is None


def test_verdict_accepts_an_explicit_draft_reply() -> None:
    """When present, draft_reply round-trips through validation."""
    verdict = Verdict.model_validate(_verdict_json(draft_reply="Friday 2pm works for me."))

    assert verdict.draft_reply == "Friday 2pm works for me."


def test_verdict_metadata_defaults_to_an_empty_dict_when_omitted() -> None:
    """metadata is optional freeform extraction (docs/DESIGN.md §10.1) —
    omitting it entirely from the response is valid, same convention
    as draft_reply."""
    verdict = Verdict.model_validate(_verdict_json())

    assert verdict.metadata == {}


def test_verdict_accepts_freeform_metadata_key_value_pairs() -> None:
    """A model may surface arbitrary extracted data (dates, order
    numbers, reference ids) via metadata — not a closed set, unlike
    category/suggested_action.mailbox."""
    verdict = Verdict.model_validate(
        _verdict_json(metadata={"order_number": "A-1234", "due_date": "2026-08-20"})
    )

    assert verdict.metadata == {"order_number": "A-1234", "due_date": "2026-08-20"}


def test_verdict_rejects_unknown_fields() -> None:
    """extra="forbid": a response with a field spork never asked for
    is a schema failure, not silently ignored — same rule as
    rules.schema.Condition/Action for a hand-edited rules.toml."""
    with pytest.raises(ValidationError):
        Verdict.model_validate(_verdict_json(unexpected_field="surprise"))


def test_verdict_rejects_a_missing_required_field() -> None:
    """A response missing a required field (here, `reasoning`) is a
    validation failure, not a Verdict with a silently-defaulted field."""
    payload = _verdict_json()
    del payload["reasoning"]

    with pytest.raises(ValidationError):
        Verdict.model_validate(payload)
