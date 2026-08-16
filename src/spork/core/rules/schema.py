"""Pydantic models for a single rule, as loaded from `rules.toml`.

Kept as data (validated by pydantic) rather than executable code on
purpose: a `Condition` is a closed set of fields, never an arbitrary
predicate function, so a rule file from disk can be validated and
dry-run without ever calling `eval`/`exec` on anything a user wrote
(docs/DESIGN.md §7.5, §11).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Condition(BaseModel):
    """A single rule's `when` clause — a closed, declarative predicate.

    Each field is one independent kind of match; in practice a rule
    sets exactly one. `always` is the universal fallback used by a
    catch-all rule (docs/DESIGN.md §7.5's `default-escalate` example).
    New condition kinds are added here deliberately slowly — every one
    added is a new thing `spork.core.rules.engine` must know how to
    evaluate, and a new thing that's safe to run against untrusted
    rule files.
    """

    # extra="forbid": a hand-edited rules.toml with a typo'd field
    # (e.g. "enalbed" instead of "enabled") must be rejected loudly,
    # not silently ignored while the mistyped field quietly falls back
    # to its default — that's exactly the kind of mistake that makes a
    # rule behave differently from what its author intended.
    model_config = ConfigDict(extra="forbid")

    always: bool = False
    from_domain_in: list[str] | None = None
    # Exact-address match, distinct from from_domain_in — the VIP-sender
    # condition kind: "this specific mailbox," not "anyone at this domain."
    from_in: list[str] | None = None
    # Resolved by calling the configured local classifier (§9.1) once
    # per message and checking whether its category is in this list —
    # this is the one condition kind whose result depends on which
    # TextClassifier backend is configured, not just the message itself.
    local_classifier_category_in: list[str] | None = None


class Action(BaseModel):
    """A matched rule's effect: a terminal mailbox action, or escalation.

    `type == "escalate"` hands the message to Tier 2 (Claude) instead
    of applying a mailbox mutation directly (docs/DESIGN.md §9);
    `mailbox` is meaningful for `move`/`tag` and ignored otherwise.
    `reason` is free text carried through to the audit log so a
    human reviewing `spork logs` can see *why* a rule escalated or
    acted, not just that it did. `type == "archive_receipt"`
    (docs/DESIGN.md §9.5, M10) hands the message to its own pipeline
    branch — company/date extraction, keyword tagging, and combined-PDF
    archiving — never `ActionExecutor`'s plain `ActionApplier` path;
    `mailbox` is unused for it, same as `escalate`.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["move", "tag", "escalate", "ignore", "archive_receipt"]
    mailbox: str | None = None
    reason: str | None = None
    # Opts an escalation into an immediate alert (docs/DESIGN.md §12.2)
    # rather than waiting for Tier 2's verdict — a flag any escalation
    # rule can set, not hardcoded to VIP-sender identity specifically.
    alert_immediately: bool = False


class Rule(BaseModel):
    """One user-authored condition -> action mapping from `rules.toml`.

    `id` is the stable handle audit-log entries and
    `spork rules enable/disable <id>` refer to, so it must be unique
    and is never regenerated. `enabled` exists so a rule can be
    authored, reviewed, and dry-run (`spork rules test`) before it's
    allowed to affect real mail.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str = ""
    when: Condition
    action: Action
    enabled: bool = True
