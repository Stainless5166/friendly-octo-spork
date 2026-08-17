"""The Tier 2 fallback for company/date extraction (docs/DESIGN.md §9.5, §10.5).

A narrower Protocol than `spork.core.llm.base.LLMClient` — it answers
one closed question ("what company, what date") for a message a Tier 1
rule has already decided is a receipt, not "how should this message be
handled." Reusing the general-purpose `Verdict` schema would pollute
every other category with two fields only receipts need; this mirrors
`LLMClient`'s own adapter pattern (§10.1) at its own, smaller scope.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from spork.core.receipts.extract import ReceiptExtraction


@dataclass(frozen=True, slots=True)
class ReceiptExtractionRequest:
    """Everything a ReceiptExtractionClient needs to extract one
    receipt's company/date — spork's own internally-constructed input,
    never untrusted external data, same reasoning as `VerdictRequest`
    (§10.1)."""

    subject: str
    from_address: str
    from_domain: str
    body_text: str


@dataclass(frozen=True, slots=True)
class ReceiptExtractionUsage:
    """Token counts from one extraction call, mirroring `LLMCallUsage`."""

    tokens_in: int
    tokens_out: int


@dataclass(frozen=True, slots=True)
class ReceiptExtractionResult:
    """The extraction and its usage, returned across the
    ReceiptExtractionClient boundary — mirrors `LLMResult`."""

    extraction: ReceiptExtraction
    usage: ReceiptExtractionUsage


class ReceiptExtractionClient(Protocol):
    """What every Tier 2 receipt-extraction backend adapts to.

    A `Protocol`, not an ABC — a backend never needs to import or
    inherit from anything here to satisfy it, same as `LLMClient`/
    `Provider`/`Alerter`.
    """

    def extract_receipt(self, request: ReceiptExtractionRequest) -> ReceiptExtractionResult: ...


class RecordedReceiptExtractionsLoadError(ValueError):
    """Raised when a recorded-extractions JSON file can't be parsed.

    Covers a missing file, malformed JSON, a non-object top level, and
    an entry missing a required field — one catchable type, same
    fail-loud pattern as `RecordedResponsesLoadError` (§10.5).
    """


class UnrecordedReceiptExtractionError(KeyError):
    """Raised when a ReceiptExtractionRequest has no matching recorded
    extraction. Names the domains that *were* recorded — same
    "name what's available" shape as `UnrecordedResponseError`."""


def load_recorded_receipt_extractions(path: str | Path) -> dict[str, ReceiptExtraction]:
    """Parse a JSON object of {from_domain: {"company": ..., "date": ...}}
    into `ReceiptExtraction`s, keyed by domain — a fixture entry
    describes "how spork resolves this sender," not one specific
    email, so domain (not subject) is the natural key here, unlike
    `load_recorded_responses()`.
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise RecordedReceiptExtractionsLoadError(f"responses file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RecordedReceiptExtractionsLoadError(f"invalid JSON in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise RecordedReceiptExtractionsLoadError(
            f"{path} must contain a JSON object keyed by from_domain, got {type(raw).__name__}"
        )

    extractions: dict[str, ReceiptExtraction] = {}
    for domain, entry in raw.items():
        if not isinstance(entry, dict) or "company" not in entry or "date" not in entry:
            raise RecordedReceiptExtractionsLoadError(
                f"{path}: recorded extraction for {domain!r} must be an object with "
                f"'company' and 'date', got {entry!r}"
            )
        extractions[domain] = ReceiptExtraction(company=entry["company"], date=entry["date"])

    return extractions


class RecordedReceiptExtractionClient:
    """Replays a fixed set of pre-recorded extractions, keyed by
    `ReceiptExtractionRequest.from_domain` — the ReceiptExtractionClient
    equivalent of `RecordedLLMClient` (§10.5): a second, fully real
    adapter with no `NotImplementedError` anywhere, for CI and offline
    acceptance runs. Not a way to fake a live extraction for
    production use, same caveat `RecordedLLMClient` states.
    """

    def __init__(self, responses_path: str | Path) -> None:
        self._extractions = load_recorded_receipt_extractions(responses_path)

    def extract_receipt(self, request: ReceiptExtractionRequest) -> ReceiptExtractionResult:
        try:
            extraction = self._extractions[request.from_domain]
        except KeyError as exc:
            raise UnrecordedReceiptExtractionError(
                f"no recorded extraction for domain {request.from_domain!r}; "
                f"known domains: {sorted(self._extractions)}"
            ) from exc
        return ReceiptExtractionResult(
            extraction=extraction, usage=ReceiptExtractionUsage(tokens_in=0, tokens_out=0)
        )
