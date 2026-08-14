"""Acceptance tests for the exact LiteLLM prompt and tool contract (§10.1)."""

from __future__ import annotations

import json

from spork.core.llm.base import Verdict, VerdictRequest
from spork.core.llm.prompt import build_prompt


def _request() -> VerdictRequest:
    return VerdictRequest(
        subject="Re: Thursday call",
        from_address="client@example.com",
        to_addresses=("me@example.com", "assistant@example.com"),
        cleaned_body="Can we move Thursday's call to Friday at 2pm?",
        thread_prior_subject="Thursday call",
        thread_user_has_replied=True,
        available_mailboxes=("Inbox", "Needs-Reply"),
    )


def test_build_prompt_contains_the_complete_message_context() -> None:
    """The full, cleaned request is visible in the exact messages sent upstream."""
    prompt = build_prompt(_request())

    assert prompt.messages == (
        {
            "role": "system",
            "content": (
                "You are Spork's Tier 2 email triage classifier. "
                "Call deliver_verdict exactly once. Choose category and mailbox only "
                "from the values supplied in the user message. Never send email."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "available_mailboxes": ["Inbox", "Needs-Reply"],
                    "cleaned_body": "Can we move Thursday's call to Friday at 2pm?",
                    "from_address": "client@example.com",
                    "subject": "Re: Thursday call",
                    "thread_prior_subject": "Thursday call",
                    "thread_user_has_replied": True,
                    "to_addresses": ["me@example.com", "assistant@example.com"],
                },
                sort_keys=True,
            ),
        },
    )


def test_build_prompt_forces_one_deliver_verdict_tool_with_the_verdict_schema() -> None:
    """Tool calling, not free-form JSON, is the settled production contract."""
    prompt = build_prompt(_request())

    assert prompt.tools == (
        {
            "type": "function",
            "function": {
                "name": "deliver_verdict",
                "description": "Return Spork's validated Tier 2 verdict for this email.",
                "parameters": Verdict.model_json_schema(),
            },
        },
    )
    assert prompt.tool_choice == {"type": "function", "function": {"name": "deliver_verdict"}}
