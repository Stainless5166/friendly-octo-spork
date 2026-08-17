"""The known-sender registry's pure logic (docs/DESIGN.md §9.5).

Storage lives directly on `StateDB` (`get_known_sender()`/
`learn_known_sender()`, `known_receipt_senders` table) — the same
one-class-owns-every-table convention `push_cursor`/`processed_messages`/
`llm_usage` already follow, not a separate wrapper class. This module
holds what's left once storage is factored out: normalizing a sender
domain to one canonical key, the same "pure logic decoupled from
StateDB" split `spork.core.llm.budget.has_budget_remaining()` already
uses for `LLMUsage`.
"""

from __future__ import annotations


def normalize_sender_domain(from_domain: str) -> str:
    """Canonicalize a sender domain for registry lookups/writes.

    Lowercased and stripped so `Billing.AcmeCloud.com` (however a
    message's `From` header happened to be cased) and a seeded
    `billing.acmecloud.com` entry always agree on the same key — a
    real gap otherwise: JMAP/mail senders don't guarantee consistent
    domain casing, and a case-sensitive miss here would silently
    re-trigger Tier 2 for a sender spork already learned.
    """
    return from_domain.strip().lower()
