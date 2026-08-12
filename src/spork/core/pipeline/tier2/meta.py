"""Tier2Meta: the concrete metadata type the Tier 2 pipeline uses (§10.7).

The Tier 2 sibling to spork.core.pipeline.meta.MessageMeta — one more
concrete use of the generic spork.core.pipeline.core framework, kept
as its own type rather than folded into MessageMeta since RuleVerdict
(Tier 1) and llm.base.Verdict (Tier 2) are different shapes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from spork.core.llm.base import Verdict, VerdictRequest
from spork.core.llm.confidence import ConfidenceBand
from spork.core.models import NormalizedMessage


@dataclass(frozen=True, slots=True)
class Tier2Meta:
    """Everything a Tier 2 pipeline module might read or set.

    `message`/`to_addresses`/`thread_prior_subject`/
    `thread_user_has_replied`/`available_mailboxes` are caller-supplied
    (like `MessageMeta.rules`) — this pipeline doesn't parse a real
    "to" header or thread history out of `NormalizedMessage` itself,
    it consumes whatever already-resolved values it's given. The rest
    are unset (`None`) until the module responsible for them has run.
    """

    message: NormalizedMessage
    to_addresses: Sequence[str]
    thread_prior_subject: str | None
    thread_user_has_replied: bool
    available_mailboxes: Sequence[str]
    ts: str | None = None
    request: VerdictRequest | None = None
    verdict: Verdict | None = None
    band: ConfidenceBand | None = None
    audit_event: str | None = None
    audit_detail_json: str | None = None
