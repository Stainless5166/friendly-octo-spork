"""Dynamically load a ReceiptExtractionClient adapter at runtime (docs/DESIGN.md §9.5, M10).

A receipt extraction client is named in config as a "module.path:ClassName"
spec and resolved via `importlib` at startup — identical mechanics to
`spork.core.context.loader.load_context_provider`/
`spork.core.llm.loader.load_llm_client`: a backend's dependencies only
get imported if that backend is actually configured.
"""

from __future__ import annotations

import importlib
from typing import Any

from spork.core.receipts.llm import ReceiptExtractionClient


class ReceiptExtractionClientLoadError(Exception):
    """Raised when a ReceiptExtractionClient spec can't be resolved to a usable client.

    Covers every way loading can fail (malformed spec, unimportable
    module, missing class, a constructor that rejects the given
    config) as one type, mirroring `ContextProviderLoadError`/
    `LLMClientLoadError` — callers only need to catch one thing.
    """


def load_receipt_extraction_client(spec: str, /, **kwargs: Any) -> ReceiptExtractionClient:
    """Load and construct a ReceiptExtractionClient from a "module.path:ClassName" spec.

    `kwargs` pass straight through to the client's constructor — this
    function doesn't know or care what any given backend's constructor
    needs.
    """
    module_path, sep, class_name = spec.partition(":")
    if not sep:
        raise ReceiptExtractionClientLoadError(
            f"invalid receipt extraction client spec {spec!r}; expected 'module.path:ClassName'"
        )

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ReceiptExtractionClientLoadError(
            f"could not import receipt extraction client module {module_path!r}: {exc}"
        ) from exc

    try:
        client_cls = getattr(module, class_name)
    except AttributeError as exc:
        raise ReceiptExtractionClientLoadError(
            f"module {module_path!r} has no attribute {class_name!r}"
        ) from exc

    try:
        client: ReceiptExtractionClient = client_cls(**kwargs)
    except Exception as exc:
        raise ReceiptExtractionClientLoadError(
            f"could not construct receipt extraction client {spec!r}: {exc}"
        ) from exc
    return client
