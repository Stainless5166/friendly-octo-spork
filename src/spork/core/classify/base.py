"""The contract every local classifier backend must satisfy.

This module intentionally has no dependency on *how* a backend
classifies — see docs/DESIGN.md §9.1. Anything importing
`TextClassifier` should be able to work with a keyword-matching
implementation today and a local ML model tomorrow without changing a
line of its own code.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from spork.core.models import NormalizedMessage


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Output of one local classification pass over one message.

    `category` is a single best-guess label whose vocabulary is
    backend-defined (not a shared enum) — forcing every backend into
    one fixed label set would defeat the point of making backends
    swappable. `scores` is an open bag so a backend can also expose
    finer-grained signals (e.g. `{"urgent": 0.9}`) that a rule
    condition or a future tuning pass can key off, without every
    backend having to agree on which signals exist.
    """

    category: str
    scores: Mapping[str, float] = field(default_factory=dict)


class TextClassifier(Protocol):
    """Structural contract for a local (non-LLM) message classifier.

    A `Protocol`, not an ABC: backends register a plain class (or
    factory) with `spork.core.classify.registry` and never need to
    import or inherit from anything in this package to satisfy it —
    keeps the barrier to adding a new experimental backend as low as
    possible.
    """

    def classify(self, message: NormalizedMessage) -> ClassificationResult:
        """Score/label `message`. Must be local and fast: no network
        calls, no LLM — that's what Tier 2 (spork.core.llm) is for."""
        ...
