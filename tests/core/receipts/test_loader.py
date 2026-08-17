"""Acceptance tests for the dynamic ReceiptExtractionClient loader (docs/DESIGN.md §9.5, M10).

Mirrors tests/core/context/test_loader.py exactly — same import/
instantiate mechanics, just for ReceiptExtractionClient specs.
"""

from __future__ import annotations

import pytest

from spork.core.receipts.loader import (
    ReceiptExtractionClientLoadError,
    load_receipt_extraction_client,
)


class _FixtureReceiptExtractionClient:
    """A minimal stand-in satisfying ReceiptExtractionClient, used only
    to prove the loader's import/instantiate mechanics work — never a
    real backend."""

    def __init__(self, label: str = "default") -> None:
        self.label = label

    def extract_receipt(self, request: object) -> object:  # pragma: no cover - never called
        raise NotImplementedError


def test_load_receipt_extraction_client_imports_and_instantiates_by_spec() -> None:
    client = load_receipt_extraction_client(f"{__name__}:_FixtureReceiptExtractionClient")

    assert isinstance(client, _FixtureReceiptExtractionClient)
    assert client.label == "default"


def test_load_receipt_extraction_client_passes_through_constructor_kwargs() -> None:
    client = load_receipt_extraction_client(
        f"{__name__}:_FixtureReceiptExtractionClient", label="custom"
    )

    assert client.label == "custom"


def test_load_receipt_extraction_client_raises_for_malformed_spec() -> None:
    with pytest.raises(ReceiptExtractionClientLoadError):
        load_receipt_extraction_client("no-colon-in-this-spec")


def test_load_receipt_extraction_client_raises_for_an_unimportable_module() -> None:
    with pytest.raises(ReceiptExtractionClientLoadError):
        load_receipt_extraction_client("spork.core.receipts.nonexistent_module:Whatever")


def test_load_receipt_extraction_client_raises_for_a_missing_class() -> None:
    with pytest.raises(ReceiptExtractionClientLoadError):
        load_receipt_extraction_client(f"{__name__}:NoSuchClass")


def test_load_receipt_extraction_client_can_load_the_real_recorded_client(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Not just fixture mechanics -- proves the loader can actually
    resolve the one real, shipped backend."""
    import json

    responses_path = tmp_path / "extractions.json"
    responses_path.write_text(json.dumps({"acmecloud.com": {"company": "Acme Cloud", "date": "t"}}))

    client = load_receipt_extraction_client(
        "spork.core.receipts.llm:RecordedReceiptExtractionClient",
        responses_path=str(responses_path),
    )

    from spork.core.receipts.llm import RecordedReceiptExtractionClient

    assert isinstance(client, RecordedReceiptExtractionClient)
