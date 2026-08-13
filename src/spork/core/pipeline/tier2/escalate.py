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

from collections.abc import Sequence

from spork.core.actions.executor import ActionExecutor
from spork.core.config.schema import TieringConfig
from spork.core.llm.base import LLMClient, Verdict
from spork.core.models import NormalizedMessage
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tier2.default import process_tier2_message
from spork.core.providers.base import DraftCreator, MailboxLister, ThreadHistoryReader
from spork.core.state.db import StateDB


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
        max_body_chars=tiering.max_body_chars,
    )
