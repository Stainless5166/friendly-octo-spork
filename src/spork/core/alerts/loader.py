"""Dynamically load an Alerter backend at runtime (docs/DESIGN.md §12.1).

An alerter is named in config as a "module.path:ClassName" spec and
resolved via `importlib` at startup — identical mechanics to
`spork.core.providers.loader.load_provider`/
`spork.core.llm.loader.load_llm_client`: a backend's dependencies
only get imported if that backend is the one actually configured.
"""

from __future__ import annotations

import importlib
from typing import Any

from spork.core.alerts.base import Alerter


class AlerterLoadError(Exception):
    """Raised when an Alerter spec can't be resolved to a usable backend.

    Covers every way loading can fail (malformed spec, unimportable
    module, missing class, a constructor that rejects the given
    config) as one type, mirroring `ProviderLoadError`/
    `LLMClientLoadError` — callers only need to catch one thing.
    """


def load_alerter(spec: str, /, **kwargs: Any) -> Alerter:
    """Load and construct an Alerter from a "module.path:ClassName" spec.

    `kwargs` pass straight through to the backend's constructor — this
    function doesn't know or care what any given backend needs.
    """
    module_path, sep, class_name = spec.partition(":")
    if not sep:
        raise AlerterLoadError(f"invalid Alerter spec {spec!r}; expected 'module.path:ClassName'")

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise AlerterLoadError(f"could not import Alerter module {module_path!r}: {exc}") from exc

    try:
        alerter_cls = getattr(module, class_name)
    except AttributeError as exc:
        raise AlerterLoadError(f"module {module_path!r} has no attribute {class_name!r}") from exc

    try:
        alerter: Alerter = alerter_cls(**kwargs)
    except TypeError as exc:
        raise AlerterLoadError(f"could not construct Alerter {spec!r}: {exc}") from exc
    return alerter
