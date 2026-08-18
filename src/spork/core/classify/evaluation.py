"""Offline metrics for tuning local classification against labeled mail."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from spork.core.classify.base import TextClassifier
from spork.core.models import NormalizedMessage


@dataclass(frozen=True, slots=True)
class LabeledMetrics:
    """Confusion counts for one classification label."""

    true_positive: int
    false_positive: int
    false_negative: int

    @property
    def precision(self) -> float:
        """Return precision, treating no predicted positives as zero."""
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        """Return recall, treating no actual positives as zero."""
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        """Return the harmonic mean of precision and recall."""
        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator else 0.0


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Aggregate primary-label accuracy and multi-label confusion metrics."""

    examples: int
    primary_accuracy: float
    labels: dict[str, LabeledMetrics]


def evaluate_classifier(
    classifier: TextClassifier,
    examples: Iterable[tuple[NormalizedMessage, frozenset[str]]],
    *,
    threshold: float = 0.5,
) -> EvaluationReport:
    """Evaluate a classifier against normalized, multi-label ground truth."""
    if not 0 <= threshold <= 1:
        raise ValueError(f"threshold must be between 0 and 1: {threshold}")

    counts: dict[str, list[int]] = {}
    total = 0
    primary_correct = 0
    for message, expected in examples:
        result = classifier.classify(message)
        predicted = {name for name, score in result.scores.items() if score >= threshold}
        if (
            result.category != "uncategorized"
            and result.scores.get(result.category, 0.0) >= threshold
        ):
            predicted.add(result.category)
        labels = expected | predicted
        for label in labels:
            true_positive, false_positive, false_negative = counts.setdefault(label, [0, 0, 0])
            if label in expected and label in predicted:
                counts[label] = [true_positive + 1, false_positive, false_negative]
            elif label in predicted:
                counts[label] = [true_positive, false_positive + 1, false_negative]
            else:
                counts[label] = [true_positive, false_positive, false_negative + 1]
        if result.category in expected:
            primary_correct += 1
        total += 1

    return EvaluationReport(
        examples=total,
        primary_accuracy=primary_correct / total if total else 0.0,
        labels={label: LabeledMetrics(*values) for label, values in sorted(counts.items())},
    )
