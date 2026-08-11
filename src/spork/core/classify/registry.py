"""Name -> TextClassifier backend lookup (docs/DESIGN.md §9.1).

This is the actual swap point: `config.toml`'s `tiering.local_classifier`
names a backend registered here, so trying a different local
classification technique is a config edit, never a code change to the
rule engine or the daemon pipeline.
"""

from __future__ import annotations

from collections.abc import Callable

from spork.core.classify.base import TextClassifier

# Factories, not instances, keyed by the name used in config.toml.
# Storing factories means registering a backend never pays its
# construction cost (e.g. loading a model file) until it's actually
# selected — most configs will only ever construct one of these.
_REGISTRY: dict[str, Callable[[], TextClassifier]] = {}


class UnknownClassifierError(KeyError):
    """Raised when config names a backend that was never registered.

    A distinct type rather than a bare KeyError so callers like
    `spork doctor` (docs/DESIGN.md §9.1's "fail loud" requirement) can
    catch precisely this and print an actionable message instead of a
    generic lookup failure.
    """


def register(name: str, factory: Callable[[], TextClassifier]) -> None:
    """Register `factory` as the classifier backend for `name`.

    Rejects re-registering an existing name rather than silently
    overwriting it — a second backend claiming a name already in use
    is almost always a bug (a duplicate import, a copy-pasted
    registration), not an intentional override.
    """
    if name in _REGISTRY:
        raise ValueError(f"classifier {name!r} is already registered")
    _REGISTRY[name] = factory


def get(name: str) -> TextClassifier:
    """Construct and return the classifier backend registered as `name`.

    Raises `UnknownClassifierError` instead of returning some default
    backend when `name` isn't registered — per §9.1, a rule that
    depends on classifier output should never silently stop being
    evaluated because of a typo in `tiering.local_classifier`.
    """
    try:
        factory = _REGISTRY[name]
    except KeyError as exc:
        known = sorted(_REGISTRY)
        raise UnknownClassifierError(
            f"no local classifier backend registered under {name!r}; known backends: {known}"
        ) from exc
    return factory()
