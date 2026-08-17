"""Transport-agnostic message representation shared across spork.core.

Everything downstream of JMAP fetching (the rule engine, local
classifiers, and eventually the LLM prompt builder) should depend on
`NormalizedMessage`, never on jmapc's wire types directly. That
indirection is what lets those pieces be unit-tested without a live
JMAP session, and keeps the mail transport itself swappable in
principle (docs/DESIGN.md §6.1).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class NormalizedMessage:
    """One email, reduced to the fields the triage pipeline actually needs.

    Frozen because a message is a fact about something that already
    arrived — nothing in the pipeline should be able to mutate the
    record it's classifying out from under later logging/auditing.
    `from_domain` is stored pre-split (rather than derived on every
    condition check) since sender-domain rules are the single most
    common Tier 1 condition (docs/DESIGN.md §7.5) and deserve to be
    cheap.
    """

    message_id: str
    thread_id: str
    from_address: str
    from_domain: str
    subject: str
    body_text: str
    headers: Mapping[str, str] = field(default_factory=dict)
    mailbox_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Attachment:
    """One email attachment, reduced to what the receipt archiver needs
    (docs/DESIGN.md §9.5) — filename/content type for placement
    decisions, raw bytes for rendering. Transport-agnostic like
    `NormalizedMessage`: `Provider.build_attachment_fetcher()` (§9.3)
    is the only thing that produces these, so nothing downstream needs
    to know whether they came from a JMAP blob fetch or a local fixture
    file.
    """

    filename: str
    content_type: str
    data: bytes
