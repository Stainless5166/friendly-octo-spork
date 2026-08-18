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
    `BackendSpec` came from. `kwargs` contains ordinary constructor
    values; `secret_kwargs` maps constructor arguments to SecretSpec
    field names that runtime composition resolves only in memory.
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


class ReceiptArchiveConfig(BaseModel):
    """The `[receipt_archive]` table (docs/DESIGN.md §9.5, M10) — where
    `archive_receipt` rule actions save their combined PDFs and which
    `ReceiptExtractionClient` backend answers the one narrow Tier 2
    fallback call. `None` (`SporkConfig.receipt_archive`'s default)
    means the feature is off entirely: an `archive_receipt` rule with
    no `[receipt_archive]` configured is a real config error at
    pipeline composition, same "fail loud on a real gap" stance as
    every other required-but-unset config dependency in this codebase.
    `extraction` has no default for the same reason `provider`/`llm`/
    `alerts` don't on `SporkConfig` itself — it must be explicit.
    """

    model_config = ConfigDict(extra="forbid")

    output_dir: Path
    extraction: BackendSpec


class ClassificationDestinationConfig(BaseModel):
    """One classification-to-mailbox/tag threshold mapping."""

    model_config = ConfigDict(extra="forbid")

    destination: str
    minimum_score: float = Field(0, ge=0, le=100)


class ClassificationConfig(BaseModel):
    """The policy that turns classification evidence into destinations."""

    model_config = ConfigDict(extra="forbid")

    mailboxes: dict[str, ClassificationDestinationConfig] = Field(default_factory=dict)
    tags: dict[str, ClassificationDestinationConfig] = Field(default_factory=dict)


class TieringConfig(BaseModel):
    """The `[tiering]` table — Tier 1/Tier 2 thresholds and policy.

    Every field has a default matching §7.2's example config.toml, so
    omitting `[tiering]` entirely is a valid, fully-specified config,
    not a missing-field error.
    """

    model_config = ConfigDict(extra="forbid")

    default_unmatched_action: Literal["escalate", "ignore"] = "ignore"
    # Explicit release gate: Tier 1 beta configs set this false so an
    # escalation rule cannot silently activate a model path.
    tier2_enabled: bool = True
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
    whichever tier(s) it uses. `llm_recording=None` disables private
    corpus recording. `socket_path=None` means "not
    overridden by any tier" — `spork.core.config.loader.load_config()`
    fills it in via `paths.resolve_socket_path()` when still `None`
    after merging all three tiers, so this schema itself never needs
    to know about environment variables.
    """

    model_config = ConfigDict(extra="forbid")

    provider: BackendSpec
    llm: BackendSpec
    alerts: BackendSpec
    # None means "no knowledgebase configured" — a real, valid state
    # (spork.core.context.clients.null.NullContextProvider), not a
    # missing-field error, same convention as tiering.local_classifier.
    context: BackendSpec | None = None
    llm_recording: LLMRecordingConfig | None = None
    # None means receipt archiving is off entirely (§9.5, M10) — same
    # "unset is a real, valid state" convention as context/local_classifier.
    receipt_archive: ReceiptArchiveConfig | None = None
    classification: ClassificationConfig = Field(default_factory=ClassificationConfig)
    rules_path: Path
    db_path: Path
    socket_path: Path | None = None
    tiering: TieringConfig = Field(default_factory=TieringConfig)
    # sporkd's own operational log verbosity (§6.2, M7) — distinct from
    # audit_log (§7.4), which always records regardless of this value.
    # Overridden by `sporkd --log-level` when given, never merged with it.
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
