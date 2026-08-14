"""Build the exact messages and forced verdict tool sent through LiteLLM (§10.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from spork.core.llm.base import Verdict, VerdictRequest


@dataclass(frozen=True, slots=True)
class CompletionPrompt:
    """Provider-neutral completion arguments retained for precise corpus recording."""

    messages: tuple[dict[str, object], ...]
    tools: tuple[dict[str, object], ...]
    tool_choice: dict[str, object]


def build_prompt(request: VerdictRequest) -> CompletionPrompt:
    """Represent every request field and force one schema-validated verdict tool call."""
    user_content = json.dumps(
        {
            "available_mailboxes": list(request.available_mailboxes),
            "cleaned_body": request.cleaned_body,
            "from_address": request.from_address,
            "subject": request.subject,
            "thread_prior_subject": request.thread_prior_subject,
            "thread_user_has_replied": request.thread_user_has_replied,
            "to_addresses": list(request.to_addresses),
        },
        sort_keys=True,
    )
    return CompletionPrompt(
        messages=(
            {
                "role": "system",
                "content": (
                    "You are Spork's Tier 2 email triage classifier. "
                    "Call deliver_verdict exactly once. Choose category and mailbox only "
                    "from the values supplied in the user message. Never send email."
                ),
            },
            {"role": "user", "content": user_content},
        ),
        tools=(
            {
                "type": "function",
                "function": {
                    "name": "deliver_verdict",
                    "description": "Return Spork's validated Tier 2 verdict for this email.",
                    "parameters": Verdict.model_json_schema(),
                },
            },
        ),
        tool_choice={"type": "function", "function": {"name": "deliver_verdict"}},
    )
