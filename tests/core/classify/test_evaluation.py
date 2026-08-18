"""Tests for labeled local-classifier evaluation metrics."""

from __future__ import annotations

from dataclasses import dataclass

from spork.core.classify.base import ClassificationResult
from spork.core.classify.evaluation import evaluate_classifier


@dataclass(frozen=True)
class StubClassifier:
    """Return one deterministic result per message subject."""

    results: dict[str, ClassificationResult]

    def classify(self, message):
        return self.results[message.subject]


def test_evaluation_reports_accuracy_and_per_label_metrics(make_message) -> None:
    examples = [
        (make_message(subject="one"), frozenset({"banking"})),
        (make_message(subject="two"), frozenset({"alert"})),
        (make_message(subject="three"), frozenset({"banking"})),
    ]
    classifier = StubClassifier(
        {
            "one": ClassificationResult("banking", {"banking": 1.0}),
            "two": ClassificationResult("banking", {"banking": 1.0, "alert": 0.8}),
            "three": ClassificationResult("alert", {"alert": 0.8}),
        }
    )

    report = evaluate_classifier(classifier, examples, threshold=0.7)

    assert report.examples == 3
    assert report.primary_accuracy == 1 / 3
    assert report.labels["banking"].true_positive == 1
    assert report.labels["banking"].false_positive == 1
    assert report.labels["banking"].false_negative == 1
    assert report.labels["alert"].true_positive == 1


def test_evaluation_excludes_scores_below_threshold(make_message) -> None:
    examples = [(make_message(subject="one"), frozenset({"security"}))]
    classifier = StubClassifier({"one": ClassificationResult("security", {"security": 0.4})})

    report = evaluate_classifier(classifier, examples, threshold=0.5)

    assert report.labels["security"].true_positive == 0
    assert report.labels["security"].false_negative == 1
