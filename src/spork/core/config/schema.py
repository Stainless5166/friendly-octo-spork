"""Pydantic models for config.toml (docs/DESIGN.md §7.2).

Kept as data (validated by pydantic), same rationale as
`spork.core.rules.schema.Condition`/`Action`/`Rule`: `extra="forbid"`
everywhere, so a hand-edited config.toml with a typo'd key is rejected
loudly rather than silently ignored.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BackendSpec(BaseModel):
    """A dynamically-loaded backend's spec + constructor kwargs.

    Matches `load_provider()`/`load_llm_client()`/`load_alerter()`'s
    "module.path:ClassName" convention exactly (§9.3/§10.1/§12.1) —
    `spec` is passed straight to whichever loader owns the field this
    `BackendSpec` came from, `kwargs` straight to that backend's
    constructor.
    """

    model_config = ConfigDict(extra="forbid")

    spec: str
    kwargs: dict[str, Any] = Field(default_factory=dict)
    secret_kwargs: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def disallow_overlapping_kwargs(self) -> Self:
        """Keep each constructor argument in one unambiguous source."""
        overlap = self.kwargs.keys() & self.secret_kwargs.keys()
        if overlap:
            joined = ", ".join(sorted(overlap))
            raise ValueError(f"kwargs and secret_kwargs overlap: {joined}")
        return self


class LLMRecordingConfig(BaseModel):
    """Select the private corpus path for recorded LLM exchanges."""

    model_config = ConfigDict(extra="forbid")

    corpus_path: Path


class TieringConfig(BaseModel):
    """The `[tiering]` table — Tier 1/Tier 2 thresholds and policy.

    Every field has a default matching §7.2's example config.toml, so
    omitting `[tiering]` entirely is a valid, fully-specified config,
    not a missing-field error.
    """

    model_config = ConfigDict(extra="forbid")

    default_unmatched_action: Literal["escalate", "ignore"] = "escalate"
    alert_threshold: float = 0.55
    autoact_threshold: float = 0.85
    daily_call_budget: int = 200
    max_body_chars: int = 4000
    # Name registered in classify/registry.py (§9.1) — None means no
    # local classifier configured, so any rule condition needing one
    # fails loudly at evaluation time (rules.engine's existing
    # behavior), not silently here.
    local_classifier: str | None = None
    allowed_categories: list[str] = Field(default_factory=list)


class SporkConfig(BaseModel):
    """The fully-merged, validated shape of config.toml (§7.2).

    `provider`/`llm`/`alerts`/`rules_path`/`db_path` have no static
    default — every real deployment must specify them, across
    whichever tier(s) it uses. `socket_path=None` means "not
    overridden by any tier" — `spork.core.config.loader.load_config()`
    fills it in via `paths.resolve_socket_path()` when still `None`
    after merging all three tiers, so this schema itself never needs
    to know about environment variables.
    """

    model_config = ConfigDict(extra="forbid")

    provider: BackendSpec
    llm: BackendSpec
    alerts: BackendSpec
    llm_recording: LLMRecordingConfig | None = None
    rules_path: Path
    db_path: Path
    socket_path: Path | None = None
    tiering: TieringConfig = Field(default_factory=TieringConfig)
    # sporkd's own operational log verbosity (§6.2, M7) — distinct from
    # audit_log (§7.4), which always records regardless of this value.
    # Overridden by `sporkd --log-level` when given, never merged with it.
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
