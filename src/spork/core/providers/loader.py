"""Dynamically load a Provider adapter at runtime (docs/DESIGN.md §9.3).

A provider is named in config as a "module.path:ClassName" spec and
resolved via `importlib` at startup — the same modularity approach as
`spork.core.classify.registry`, except providers are never eagerly
imported: a provider's dependencies (`jmapc`, an eventual IMAP
library) only get imported if that provider is the one actually
configured.
"""

from __future__ import annotations

import importlib
from typing import Any

from spork.core.providers.base import Provider


class ProviderLoadError(Exception):
    """Raised when a provider spec can't be resolved to a usable Provider.

    Covers every way loading can fail (malformed spec, unimportable
    module, missing class, a constructor that rejects the given
    config) as one type, so callers (`spork doctor`, M5) only need to
    catch one thing — the same fail-loud pattern as the rest of
    `spork.core` (`UnknownClassifierError`, etc.).
    """


def load_provider(spec: str, /, **kwargs: Any) -> Provider:
    """Load and construct a Provider from a "module.path:ClassName" spec.

    `kwargs` pass straight through to the provider's constructor (e.g.
    `host=`/`api_token=` for `JmapProvider`) — this function doesn't
    know or care what any given provider's constructor needs.
    """
    module_path, sep, class_name = spec.partition(":")
    if not sep:
        raise ProviderLoadError(f"invalid provider spec {spec!r}; expected 'module.path:ClassName'")

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ProviderLoadError(f"could not import provider module {module_path!r}: {exc}") from exc

    try:
        provider_cls = getattr(module, class_name)
    except AttributeError as exc:
        raise ProviderLoadError(f"module {module_path!r} has no attribute {class_name!r}") from exc

    try:
        provider: Provider = provider_cls(**kwargs)
    except TypeError as exc:
        raise ProviderLoadError(f"could not construct provider {spec!r}: {exc}") from exc
    return provider
