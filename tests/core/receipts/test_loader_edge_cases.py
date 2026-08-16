"""Failure/edge-case tests for the ReceiptExtractionClient loader.

Companion to test_loader.py's acceptance tests.
"""

from __future__ import annotations

import pytest
from spork.core.receipts.loader import (
    ReceiptExtractionClientLoadError,
    load_receipt_extraction_client,
)


class _FixtureReceiptExtractionClient:
    def __init__(self, label: str = "default") -> None:
        self.label = label


def test_load_receipt_extraction_client_raises_when_construction_fails() -> None:
    """A client whose constructor rejects the given kwargs (e.g. a
    typo'd config key) fails loudly rather than a raw TypeError
    leaking through unwrapped."""
    with pytest.raises(ReceiptExtractionClientLoadError):
        load_receipt_extraction_client(
            f"{__name__}:_FixtureReceiptExtractionClient", unexpected_kwarg=True
        )
