"""Dynamically load a ContextProvider adapter at runtime (docs/DESIGN.md §10.8).

A context provider is named in config as a "module.path:ClassName"
spec and resolved via `importlib` at startup — identical mechanics to
`spork.core.llm.loader.load_llm_client`/`spork.core.providers.loader.load_provider`:
a backend's dependencies only get imported if that backend is
actually configured.
"""

from __future__ import annotations

import importlib
from typing import Any

from spork.core.context.base import ContextProvider


class ContextProviderLoadError(Exception):
    """Raised when a ContextProvider spec can't be resolved to a usable provider.

    Covers every way loading can fail (malformed spec, unimportable
    module, missing class, a constructor that rejects the given
    config) as one type, mirroring `LLMClientLoadError`/`ProviderLoadError`
    — callers only need to catch one thing.
    """


def load_context_provider(spec: str, /, **kwargs: Any) -> ContextProvider:
    """Load and construct a ContextProvider from a "module.path:ClassName" spec.

    `kwargs` pass straight through to the provider's constructor —
    this function doesn't know or care what any given provider's
    constructor needs.
    """
    module_path, sep, class_name = spec.partition(":")
    if not sep:
        raise ContextProviderLoadError(
            f"invalid context provider spec {spec!r}; expected 'module.path:ClassName'"
        )

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ContextProviderLoadError(
            f"could not import context provider module {module_path!r}: {exc}"
        ) from exc

    try:
        provider_cls = getattr(module, class_name)
    except AttributeError as exc:
        raise ContextProviderLoadError(
            f"module {module_path!r} has no attribute {class_name!r}"
        ) from exc

    try:
        provider: ContextProvider = provider_cls(**kwargs)
    except Exception as exc:
        raise ContextProviderLoadError(
            f"could not construct context provider {spec!r}: {exc}"
        ) from exc
    return provider
