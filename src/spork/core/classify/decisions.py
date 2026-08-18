"""Shared classification evidence and the policy boundary before actions."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256

from spork.core.models import NormalizedMessage


@dataclass(frozen=True, slots=True)
class Classification:
    """One named classification score carried between pipeline stages."""

    name: str
    score: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("classification name must not be empty")
        if not 0 <= self.score <= 100:
            raise ValueError(f"classification score must be between 0 and 100: {self.score}")


@dataclass(frozen=True, slots=True)
class DestinationPolicy:
    """Maps an eligible classification to one mailbox or tag destination."""

    destination: str
    minimum_score: float

    def __post_init__(self) -> None:
        if not self.destination:
            raise ValueError("destination must not be empty")
        if not 0 <= self.minimum_score <= 100:
            raise ValueError(f"minimum score must be between 0 and 100: {self.minimum_score}")


@dataclass(frozen=True, slots=True)
class ClassificationPolicy:
    """Separates one primary mailbox decision from additive tag decisions."""

    mailboxes: Mapping[str, DestinationPolicy] = field(default_factory=dict)
    tags: Mapping[str, DestinationPolicy] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ClassificationDecision:
    """The side-effect-free result the action planner can validate."""

    classifications: tuple[Classification, ...]
    mailbox: str | None
    tags: tuple[str, ...]


def exact_duplicate_key(message: NormalizedMessage) -> str:
    """Return a stable local key for exact sender/subject/body duplicates."""
    normalized_subject = re.sub(r"\s+", " ", message.subject).strip().casefold()
    normalized_body = re.sub(r"\s+", " ", message.body_text).strip()
    material = "\x1f".join((message.from_address.casefold(), normalized_subject, normalized_body))
    return sha256(material.encode("utf-8")).hexdigest()


def merge_classifications(
    existing: Sequence[Classification],
    incoming: Sequence[Classification],
    *,
    minimum_score: float = 0,
) -> tuple[Classification, ...]:
    """Add qualifying evidence and retain the greatest score per name."""
    if not 0 <= minimum_score <= 100:
        raise ValueError(f"minimum score must be between 0 and 100: {minimum_score}")

    scores = {classification.name: classification.score for classification in existing}
    for classification in incoming:
        if classification.score >= minimum_score:
            scores[classification.name] = max(
                scores.get(classification.name, 0), classification.score
            )
    return tuple(Classification(name=name, score=scores[name]) for name in sorted(scores))


def decide_classifications(
    classifications: Sequence[Classification], policy: ClassificationPolicy
) -> ClassificationDecision:
    """Choose one highest-scoring mailbox and every eligible tag."""
    scores = {classification.name: classification.score for classification in classifications}
    eligible_mailboxes = [
        (scores[name], name, destination.destination)
        for name, destination in policy.mailboxes.items()
        if name in scores and scores[name] >= destination.minimum_score
    ]
    mailbox = (
        max(eligible_mailboxes, key=lambda item: (item[0], item[1]))[2]
        if eligible_mailboxes
        else None
    )
    tags = tuple(
        policy.tags[name].destination
        for name in policy.tags
        if name in scores and scores[name] >= policy.tags[name].minimum_score
    )
    return ClassificationDecision(tuple(classifications), mailbox, tags)
