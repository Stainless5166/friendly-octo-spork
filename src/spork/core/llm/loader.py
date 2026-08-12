"""Dynamically load an LLMClient adapter at runtime (docs/DESIGN.md §10.1).

An LLM client is named in config as a "module.path:ClassName" spec and
resolved via `importlib` at startup — identical mechanics to
`spork.core.providers.loader.load_provider`: a client's dependencies
(the `anthropic` SDK, an eventual other provider's SDK) only get
imported if that client is the one actually configured.
"""

from __future__ import annotations

import importlib
from typing import Any

from spork.core.llm.base import LLMClient


class LLMClientLoadError(Exception):
    """Raised when an LLMClient spec can't be resolved to a usable client.

    Covers every way loading can fail (malformed spec, unimportable
    module, missing class, a constructor that rejects the given
    config) as one type, mirroring `ProviderLoadError` — callers only
    need to catch one thing.
    """


def load_llm_client(spec: str, /, **kwargs: Any) -> LLMClient:
    """Load and construct an LLMClient from a "module.path:ClassName" spec.

    `kwargs` pass straight through to the client's constructor (e.g.
    `api_key=`/`model=` for `AnthropicLLMClient`) — this function
    doesn't know or care what any given client's constructor needs.
    """
    module_path, sep, class_name = spec.partition(":")
    if not sep:
        raise LLMClientLoadError(
            f"invalid LLM client spec {spec!r}; expected 'module.path:ClassName'"
        )

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise LLMClientLoadError(
            f"could not import LLM client module {module_path!r}: {exc}"
        ) from exc

    try:
        client_cls = getattr(module, class_name)
    except AttributeError as exc:
        raise LLMClientLoadError(f"module {module_path!r} has no attribute {class_name!r}") from exc

    try:
        client: LLMClient = client_cls(**kwargs)
    except TypeError as exc:
        raise LLMClientLoadError(f"could not construct LLM client {spec!r}: {exc}") from exc
    return client
