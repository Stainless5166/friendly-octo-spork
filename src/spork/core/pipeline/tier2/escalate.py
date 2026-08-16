"""escalate_message()/parse_to_addresses(): Tier 2 for an escalated message (§6.2.1/§13).

Extracted from what was `spork.daemon.loop`'s private
`_escalate_to_tier2()`/`_parse_to_addresses()` once `spork reclassify
<id>` needed the exact same "resolve thread history + mailbox list,
then run Tier 2" step outside the daemon loop entirely — one real
implementation, two callers (`daemon/loop.py`'s `_run_message_loop()`,
and `spork reclassify`), not a daemon-only helper duplicated for the
CLI.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from spork.core.actions.executor import ActionExecutionError, ActionExecutor
from spork.core.config.schema import TieringConfig
from spork.core.context.base import ContextProvider
from spork.core.llm.base import LLMClient, Verdict
from spork.core.llm.clients.litellm import LiteLLMClientError
from spork.core.llm.validate import VerdictValidationError
from spork.core.models import NormalizedMessage
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2.default import process_tier2_message
from spork.core.providers.base import DraftCreator, MailboxLister, ThreadHistoryReader
from spork.core.state.db import StateDB


def _utc_now_iso() -> str:
    """Default clock: an ISO 8601 UTC timestamp string, same convention
    every other module needing one (tier2/default.py, backfill.py) uses."""
    return datetime.now(UTC).isoformat()


# The "Tier 2 produced output that can't be safely used" failure class —
# not a programming bug, not an I/O failure, not budget exhaustion
# (which escalate_message() already signals via None). A live model
# call itself failing (LiteLLMClientError), a syntactically valid
# Verdict whose category/mailbox falls outside this deployment's
# configured set (VerdictValidationError), or a suggested_action that
# passed Verdict's own shape check but can't actually be executed
# (ActionExecutionError, e.g. move/tag with no mailbox — Action.mailbox
# is Optional at the pydantic level) are all the model's fault, not
# spork's. Quarantining these instead of raising is what keeps one bad
# response from crash-looping the daemon and re-burning budget on every
# restart, since a message that crashed before ever being marked
# processed just gets retried, identically, forever.
QUARANTINABLE_ERRORS: tuple[type[Exception], ...] = (
    LiteLLMClientError,
    VerdictValidationError,
    ActionExecutionError,
)


@dataclass(frozen=True, slots=True)
class QuarantinedMessage:
    """`escalate_message_or_quarantine()`'s signal that a
    `QUARANTINABLE_ERRORS` exception was caught: the message is marked
    processed and audited, but no `Verdict` was produced. Distinct from
    `escalate_message()`'s own `None` (budget exhausted) so a caller
    can tell the two apart rather than conflating "skipped, try again
    later" with "this specific message can't be processed as given"."""

    reason: str


def parse_to_addresses(message: NormalizedMessage) -> Sequence[str]:
    """Real `to_addresses`, parsed from `NormalizedMessage.headers["To"]`
    (docs/DESIGN.md §6.2.1) — comma-split, whitespace-stripped, empty
    entries dropped. `()` when there's no `To:` header at all, never a
    fabricated address.
    """
    to_header = message.headers.get("To", "")
    return tuple(addr.strip() for addr in to_header.split(",") if addr.strip())


def escalate_message(
    message: NormalizedMessage,
    *,
    thread_history_reader: ThreadHistoryReader,
    mailbox_lister: MailboxLister,
    llm_client: LLMClient,
    executor: ActionExecutor,
    draft_creator: DraftCreator,
    state_db: StateDB,
    ops: PipelineObserver,
    tiering: TieringConfig,
    context_provider: ContextProvider,
) -> Verdict | None:
    """Resolves the two Provider-supplied reads Tier 2 needs and runs
    `process_tier2_message()` for one message Tier 1 already routed to
    `"escalate"`.

    Synchronous end to end — `daemon/loop.py`'s caller wraps this whole
    function in one `asyncio.to_thread()` call so the thread-history/
    mailbox-list reads (which may themselves be real I/O against a
    live backend) run off the event-loop thread too, not just
    `process_tier2_message()` itself; `spork reclassify` calls it
    directly, since the CLI is a short-lived synchronous process with
    no event loop to keep off of.
    """
    context = thread_history_reader.get_thread_context(message)
    return process_tier2_message(
        message,
        to_addresses=parse_to_addresses(message),
        thread_prior_subject=context.prior_subject,
        thread_user_has_replied=context.user_has_replied,
        available_mailboxes=mailbox_lister.list_mailboxes(),
        llm_client=llm_client,
        executor=executor,
        draft_creator=draft_creator,
        state_db=state_db,
        ops=ops,
        allowed_categories=tiering.allowed_categories,
        daily_call_budget=tiering.daily_call_budget,
        alert_threshold=tiering.alert_threshold,
        autoact_threshold=tiering.autoact_threshold,
        context_provider=context_provider,
        max_body_chars=tiering.max_body_chars,
    )


def escalate_message_or_quarantine(
    message: NormalizedMessage,
    *,
    thread_history_reader: ThreadHistoryReader,
    mailbox_lister: MailboxLister,
    llm_client: LLMClient,
    executor: ActionExecutor,
    draft_creator: DraftCreator,
    state_db: StateDB,
    ops: PipelineObserver,
    tiering: TieringConfig,
    context_provider: ContextProvider,
    now: Callable[[], str] = _utc_now_iso,
) -> Verdict | QuarantinedMessage | None:
    """`escalate_message()`, with `QUARANTINABLE_ERRORS` caught and
    quarantined instead of propagated.

    Deliberately not a bare `except Exception` — a `StateDB`/provider
    I/O failure, or a `MissingMetaError` from a real pipeline-wiring
    bug, still propagates and takes the caller down, matching spork's
    fail-loud convention everywhere else (docs/DESIGN.md). Only the
    three specific "the model's output can't be safely used" failure
    types are caught here; this is the fix for the poison-message
    crash loop a bad live verdict could otherwise cause.
    """
    try:
        return escalate_message(
            message,
            thread_history_reader=thread_history_reader,
            mailbox_lister=mailbox_lister,
            llm_client=llm_client,
            executor=executor,
            draft_creator=draft_creator,
            state_db=state_db,
            ops=ops,
            tiering=tiering,
            context_provider=context_provider,
        )
    except QUARANTINABLE_ERRORS as exc:
        ts = now()
        reason = str(exc)
        state_db.write_audit_entry(
            ts=ts,
            jmap_id=message.message_id,
            event="tier2_quarantined",
            detail_json=json.dumps({"error_type": type(exc).__name__, "reason": reason}),
        )
        state_db.mark_processed(
            message.message_id,
            thread_id=message.thread_id,
            processed_at=ts,
            tier_reached="tier2",
            action_taken="quarantined",
        )
        ops.alert(
            uuid.uuid4().hex,
            "Tier 2 verdict quarantined",
            f"{message.subject!r} from {message.from_address}: {reason}",
            urgency="critical",
        )
        return QuarantinedMessage(reason=reason)
