"""Evaluate the local keyword classifier against the private recorded corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from spork.core.classify.evaluation import evaluate_classifier
from spork.core.classify.keyword import KeywordClassifier
from spork.core.models import NormalizedMessage

_CATEGORY_ALIASES = {
    "Newsletter": "newsletter",
    "Receipt-Invoice": "receipt",
    "Account Security Notification": "security",
    "Personal": "personal",
    "Invoice/Billing": "banking",
    "Shipping-Notification": "notification",
    "Appointment Reminder": "notification",
    "Newsletter-Notification": "newsletter",
    "Policy Update": "notification",
    "Recruiting/Job Opportunity": "personal",
    "Marketing": "newsletter",
    "Subscription Renewal Notice": "banking",
    "Meeting Invite": "notification",
}


def _examples(path: Path) -> list[tuple[NormalizedMessage, frozenset[str]]]:
    """Extract sanitized prompt messages and mapped labels from JSONL."""
    examples: list[tuple[NormalizedMessage, frozenset[str]]] = []
    for index, line in enumerate(path.read_text().splitlines()):
        entry = json.loads(line)
        payload = next(
            json.loads(item["content"])
            for item in entry["prompt"]["messages"]
            if item["role"] == "user"
        )
        address = payload["from_address"]
        message = NormalizedMessage(
            message_id=f"corpus-{index}",
            thread_id=f"corpus-thread-{index}",
            from_address=address,
            from_domain=address.rsplit("@", 1)[-1].lower(),
            subject=payload["subject"],
            body_text=payload["cleaned_body"],
        )
        examples.append((message, frozenset({_CATEGORY_ALIASES[entry["verdict"]["category"]]})))
    return examples


def main() -> None:
    """Print JSON metrics for a private corpus without logging message content."""
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    examples = _examples(args.corpus)
    classifier = KeywordClassifier()
    report = evaluate_classifier(classifier, examples, threshold=args.threshold)
    print(
        json.dumps(
            {
                "examples": report.examples,
                "primary_accuracy": report.primary_accuracy,
                "labels": {
                    name: {
                        "precision": metrics.precision,
                        "recall": metrics.recall,
                        "f1": metrics.f1,
                        "true_positive": metrics.true_positive,
                        "false_positive": metrics.false_positive,
                        "false_negative": metrics.false_negative,
                    }
                    for name, metrics in report.labels.items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.details:
        for message, expected in examples:
            result = classifier.classify(message)
            print(
                json.dumps(
                    {
                        "subject": message.subject,
                        "expected": sorted(expected),
                        "predicted": result.category,
                        "scores": result.scores,
                    },
                    sort_keys=True,
                )
            )


if __name__ == "__main__":
    main()
