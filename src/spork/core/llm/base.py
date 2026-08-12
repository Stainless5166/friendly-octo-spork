"""The common contract every Tier 2 (LLM) backend adapts to (docs/DESIGN.md §10.1).

Mirrors spork.core.providers.base's Provider pattern: Claude is the
only backend spork talks to today, but nothing downstream of
`LLMClient` should need to know that — a second backend is an
addition, not a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from spork.core.rules.schema import Action


@dataclass(frozen=True, slots=True)
class VerdictRequest:
    """Everything an LLMClient needs to produce one Verdict.

    Already assembled by the (not-yet-built) prompt-building step, so
    an LLMClient implementation never touches `NormalizedMessage` or
    the rule engine directly — just this closed, already-cleaned set
    of fields. A plain dataclass, not a pydantic model: this is
    spork's own internally-constructed input, never untrusted external
    data (`Verdict`, below, is the untrusted side).
    """

    subject: str
    from_address: str
    to_addresses: tuple[str, ...]
    cleaned_body: str
    thread_prior_subject: str | None
    thread_user_has_replied: bool
    available_mailboxes: tuple[str, ...]


class Verdict(BaseModel):
    """One Tier 2 verdict — the parsed, schema-validated form of
    docs/DESIGN.md §10's JSON output.

    A pydantic model (unlike `VerdictRequest`): this is the one place
    spork parses untrusted external structured output (an LLM's
    response), same reasoning as `rules.schema` validating a
    hand-edited `rules.toml`. `extra="forbid"` means a field the model
    invented (or a typo'd one) is a validation failure, not silently
    dropped. `suggested_action` reuses `rules.schema.Action` — the
    same terminal-action shape a Tier 1 rule produces — so
    `ActionExecutor` can consume either without knowing which tier
    produced it; `"escalate"` is rejected for it below since a verdict
    already *is* Tier 2's output, there's nowhere further to escalate
    to.

    Validating `category`/`suggested_action.mailbox` against *this
    deployment's* configured set is deliberately not this model's job
    — that's `docs/ROADMAP.md`'s separate "Verdict validation against
    configured mailbox/category set" item, since it depends on config
    this module has no access to.
    """

    model_config = ConfigDict(extra="forbid")

    category: str
    urgency: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_action: Action
    summary: str
    draft_reply: str | None = None
    reasoning: str

    @field_validator("suggested_action")
    @classmethod
    def _suggested_action_must_be_terminal(cls, action: Action) -> Action:
        """A schema-level invariant, not a deployment-specific one: a
        verdict's own suggested_action can't be "escalate" — that
        would mean Tier 2 escalating what it was already asked to
        decide on."""
        if action.type == "escalate":
            raise ValueError(
                'suggested_action.type cannot be "escalate" — Verdict is already Tier 2\'s output'
            )
        return action


class LLMClient(Protocol):
    """What every Tier 2 backend (Claude today, others later) adapts to.

    A `Protocol`, not an ABC — a backend never needs to import or
    inherit from anything here to satisfy it, same as
    `spork.core.providers.base.Provider`.
    """

    def get_verdict(self, request: VerdictRequest) -> Verdict: ...
