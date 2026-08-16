"""ArchiveReceiptAugment: the archive_receipt pipeline branch (docs/DESIGN.md §9.5, M10).

Composes every other spork.core.receipts module into one Tier-1
pipeline stage: resolve company/date (deterministic first, one narrow
Tier 2 call as fallback, learning the sender afterward), tag via
keywords, build and save a combined PDF. An `Augment` (§9.4) — it
reaches outside the payload (StateDB, the attachment fetcher, the
keyword applier, the extraction client, the filesystem), the same
signal `FetchContextAugment` (§10.8) already gives a reader.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from spork.core.pipeline.core import Payload
from spork.core.pipeline.meta import MessageMeta
from spork.core.providers.base import AttachmentFetcher, KeywordApplier
from spork.core.receipts.archive import save_pdf
from spork.core.receipts.extract import SenderDomainLookup, extract_receipt
from spork.core.receipts.llm import ReceiptExtractionClient, ReceiptExtractionRequest
from spork.core.receipts.pdf import build_receipt_pdf
from spork.core.receipts.registry import normalize_sender_domain
from spork.core.state.db import StateDB


@dataclasses.dataclass(frozen=True, slots=True)
class ReceiptArchiveComponents:
    """The collaborators `ArchiveReceiptAugment` needs, bundled so
    `build_default_pipeline()` (§9.4) only grows one new optional
    parameter — every existing caller that doesn't use receipt
    archiving stays unaffected. `domain_lookup` is optional: a curated,
    read-only domain→company source (structurally matching
    `EntityContextProvider.lookup_domain()`, M9) consulted ahead of the
    learned `StateDB` cache; omitting it just means every sender starts
    out unrecognized until spork learns it itself.
    """

    attachment_fetcher: AttachmentFetcher
    keyword_applier: KeywordApplier
    extraction_client: ReceiptExtractionClient
    output_dir: Path
    domain_lookup: SenderDomainLookup | None = None


class ArchiveReceiptAugment:
    """Handles a matched `archive_receipt` rule end to end.

    Sets `meta.audit_event`/`audit_detail_json` on success, the same
    generic contract `ApplyActionFilter` uses for `WriteAuditEntryFilter`
    to log — this stage doesn't write the audit log itself. Raises
    (rather than catching) any failure from its collaborators —
    `ReceiptArchiveError` on an unwritable output location, most
    notably — so a later stage (`WriteAuditEntryFilter`/
    `MarkProcessedFilter`) never runs and the message stays retryable,
    the same fail-open-for-retry contract `m2_rules.feature`'s
    `@audit` scenario already specifies for the terminal branch.
    """

    def __init__(self, state_db: StateDB, components: ReceiptArchiveComponents) -> None:
        self._state_db = state_db
        self._components = components

    def augment(self, payload: Payload[MessageMeta]) -> Payload[MessageMeta]:
        meta = payload.meta
        message = meta.message
        normalized_domain = normalize_sender_domain(message.from_domain)

        known_sender = self._state_db.get_known_sender(normalized_domain)
        extraction = extract_receipt(
            message, known_sender=known_sender, domain_lookup=self._components.domain_lookup
        )
        if extraction is None:
            # Deterministic path declined -- the one narrow Tier 2 call,
            # then learn the sender so the next message from this
            # domain never reaches Tier 2 again.
            request = ReceiptExtractionRequest(
                subject=message.subject,
                from_address=message.from_address,
                from_domain=message.from_domain,
                body_text=message.body_text,
            )
            result = self._components.extraction_client.extract_receipt(request)
            extraction = result.extraction
            self._state_db.learn_known_sender(
                normalized_domain,
                company=extraction.company,
                learned_from="tier2",
                learned_at=meta.ts or "",
            )

        keywords = ["receipt", f"company:{extraction.company}", f"date:{extraction.date}"]
        self._components.keyword_applier.apply_keywords(message, keywords)

        attachments = self._components.attachment_fetcher.fetch_attachments(message)
        pdf_bytes = build_receipt_pdf(
            message, attachments, company=extraction.company, date=extraction.date
        )
        saved_path = save_pdf(
            pdf_bytes,
            output_dir=self._components.output_dir,
            message_id=message.message_id,
            company=extraction.company,
            date=extraction.date,
        )

        detail_json = json.dumps(
            {
                "company": extraction.company,
                "date": extraction.date,
                "path": str(saved_path),
            }
        )
        return dataclasses.replace(
            payload,
            meta=dataclasses.replace(
                meta, audit_event="receipt_archived", audit_detail_json=detail_json
            ),
        )
