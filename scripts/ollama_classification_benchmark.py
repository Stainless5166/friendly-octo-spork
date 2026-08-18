"""Benchmark four local Ollama classifiers against an unlabeled corpus."""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from spork.core.classify.decisions import Classification
from spork.core.llm.ollama_benchmark import (
    build_benchmark_record,
    email_fingerprint,
    parse_classifications,
)

DEFAULT_CATEGORIES = (
    "banking",
    "technology",
    "alert",
    "notification",
    "security",
    "newsletter",
    "receipt",
    "urgent",
    "personal",
    "other",
)
BASELINE_ALIASES = {
    "Newsletter": "newsletter",
    "Receipt-Invoice": "receipt",
    "Account Security Notification": "security",
    "Invoice/Billing": "banking",
    "Shipping-Notification": "notification",
    "Appointment Reminder": "notification",
    "Newsletter-Notification": "newsletter",
    "Policy Update": "notification",
    "Marketing": "newsletter",
    "Subscription Renewal Notice": "banking",
    "Meeting Invite": "notification",
}
LOGGER = logging.getLogger("spork.ollama_benchmark")
CLASSIFICATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "classifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "score": {"type": "number", "minimum": 0, "maximum": 100},
                },
                "required": ["name", "score"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["classifications"],
    "additionalProperties": False,
}


def _read_corpus(path: Path, limit: int) -> list[dict[str, Any]]:
    """Read either the private unlabeled corpus or the labeled validation corpus."""
    records: list[dict[str, Any]] = []
    for index, line in enumerate(path.read_text().splitlines()):
        entry = json.loads(line)
        if "message" in entry:
            records.append(entry["message"])
            continue
        payload = next(
            json.loads(item["content"])
            for item in entry["prompt"]["messages"]
            if item["role"] == "user"
        )
        from_address = payload["from_address"]
        records.append(
            {
                "message_id": f"validation-{index + 1}",
                "from_address": from_address,
                "from_domain": from_address.rsplit("@", 1)[-1],
                "subject": payload["subject"],
                "body_text": payload["cleaned_body"],
                "headers": {},
            }
        )
    return records[:limit]


def _read_baseline(path: Path) -> dict[str, str]:
    """Map labeled corpus email fingerprints to canonical baseline labels."""
    baseline: dict[str, str] = {}
    for line in path.read_text().splitlines():
        entry = json.loads(line)
        payload = next(
            json.loads(item["content"])
            for item in entry["prompt"]["messages"]
            if item["role"] == "user"
        )
        category = str(entry["verdict"]["category"])
        canonical = BASELINE_ALIASES.get(category, category.casefold())
        baseline[
            email_fingerprint(payload["from_address"], payload["subject"], payload["cleaned_body"])
        ] = canonical
    return baseline


def _ps(api_base: str) -> dict[str, Any]:
    """Read Ollama's live model-load state, returning a safe error object."""
    try:
        request = Request(f"{api_base.rstrip('/')}/api/ps", method="GET")
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read())
        return payload if isinstance(payload, dict) else {"error": "invalid /api/ps response"}
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return {"error": f"could not read /api/ps: {exc}"}


def _message_payload(message: dict[str, Any]) -> str:
    """Build the bounded JSON input sent to one local model."""
    return json.dumps(
        {
            "from_address": message["from_address"],
            "from_domain": message["from_domain"],
            "subject": message["subject"],
            "body_text": message["body_text"],
            "headers": message.get("headers", {}),
        },
        ensure_ascii=True,
        sort_keys=True,
    )


def _extract_content(response: object) -> str:
    """Extract LiteLLM's assistant content without retaining the response object."""
    content = response.choices[0].message.content  # type: ignore[attr-defined]
    if not isinstance(content, str):
        raise ValueError("LiteLLM response content was not a string")
    return content


def _usage(response: object) -> tuple[int | None, int | None]:
    """Read optional token usage from an OpenAI-compatible response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None, None
    return (
        int(getattr(usage, "prompt_tokens", 0)),
        int(getattr(usage, "completion_tokens", 0)),
    )


def _call_model(
    completion: Any,
    *,
    model: str,
    api_base: str,
    message: dict[str, Any],
    categories: Sequence[str],
    max_tokens: int,
    keep_alive: str,
) -> tuple[tuple[Classification, ...], int | None, int | None, str | None, float]:
    """Make one JSON-only LiteLLM call and convert failures to record data."""
    started = time.perf_counter()
    try:
        response = completion(
            model=model,
            api_base=api_base,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify this email locally. Return JSON only in the form "
                        '{"classifications":[{"name":"...","score":0}]} . '
                        f"Use only these labels: {', '.join(categories)}. "
                        "Scores are 0 to 100. Include only meaningful labels."
                    ),
                },
                {"role": "user", "content": _message_payload(message)},
            ],
            temperature=0,
            max_tokens=max_tokens,
            format=CLASSIFICATION_JSON_SCHEMA,
            response_format={"type": "json_object"},
            think=False,
            keep_alive=keep_alive,
        )
        content = _extract_content(response)
        classifications = parse_classifications(content)
        tokens_in, tokens_out = _usage(response)
        error = None
    except Exception as exc:
        classifications = ()
        tokens_in, tokens_out = None, None
        error = f"{type(exc).__name__}: {exc}"
    latency_ms = (time.perf_counter() - started) * 1000
    return classifications, tokens_in, tokens_out, error, latency_ms


def _summary(records: list[dict[str, Any]], baseline: dict[str, str]) -> dict[str, Any]:
    """Aggregate comparison metrics without exposing message content."""
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_model[record["model"]].append(record)
    result: dict[str, Any] = {}
    for model, model_records in sorted(by_model.items()):
        successful = [record for record in model_records if record["error"] is None]
        labels = Counter(
            item["name"] for record in successful for item in record["classifications"]
        )
        known_labels = Counter(
            item["name"]
            for record in successful
            for item in record["classifications"]
            if item["status"] == "known"
        )
        candidate_labels = Counter(
            item["name"]
            for record in successful
            for item in record["classifications"]
            if item["status"] == "candidate"
        )
        compared = 0
        agreement = 0
        missing_predictions = 0
        primary_labels = Counter()
        confusion = Counter()
        expected_labels = Counter()
        for record in successful:
            predicted = [item for item in record["classifications"] if item["status"] == "known"]
            best: str | None = None
            if predicted:
                best = max(predicted, key=lambda item: (item["score"], item["name"]))["name"]
                primary_labels[best] += 1
            expected = baseline.get(record["fingerprint"])
            if expected is None:
                continue
            compared += 1
            expected_labels[expected.casefold()] += 1
            if not predicted:
                missing_predictions += 1
                continue
            assert best is not None
            predicted_label = best.casefold()
            expected_label = expected.casefold()
            agreement += predicted_label == expected_label
            confusion[(expected_label, predicted_label)] += 1
        baseline_distribution = Counter(baseline.values())
        total_primary = sum(primary_labels.values())
        total_baseline = sum(baseline_distribution.values())
        distribution_drift = 0.0
        if total_primary and total_baseline:
            distribution_labels = set(primary_labels) | set(baseline_distribution)
            distribution_drift = (
                sum(
                    abs(
                        primary_labels[label] / total_primary
                        - baseline_distribution[label] / total_baseline
                    )
                    for label in distribution_labels
                )
                / 2
            )
        baseline_labels = set(baseline.values())
        per_label: dict[str, dict[str, float | int]] = {}
        for label in sorted(baseline_labels | set(primary_labels)):
            true_positive = confusion[(label, label)]
            actual = expected_labels[label]
            predicted_count = primary_labels[label]
            precision = true_positive / predicted_count if predicted_count else 0.0
            recall = true_positive / actual if actual else 0.0
            per_label[label] = {
                "precision": precision,
                "recall": recall,
                "f1": (
                    2 * precision * recall / (precision + recall) if precision + recall else 0.0
                ),
                "support": actual,
            }
        result[model] = {
            "calls": len(model_records),
            "successes": len(successful),
            "errors": len(model_records) - len(successful),
            "average_latency_ms": (
                sum(record["latency_ms"] for record in model_records) / len(model_records)
            ),
            "tokens_in": sum(record["tokens_in"] or 0 for record in model_records),
            "tokens_out": sum(record["tokens_out"] or 0 for record in model_records),
            "classifications": dict(sorted(labels.items())),
            "known_classifications": dict(sorted(known_labels.items())),
            "candidate_classifications": dict(sorted(candidate_labels.items())),
            "baseline_compared": compared,
            "baseline_agreement": agreement / compared if compared else None,
            "baseline_accuracy": agreement / compared if compared else None,
            "baseline_missing_predictions": missing_predictions,
            "baseline_drift": 1 - agreement / compared if compared else None,
            "baseline_confusion": {
                f"{expected}->{predicted}": count
                for (expected, predicted), count in sorted(confusion.items())
            },
            "baseline_per_label": per_label,
            "primary_distribution": dict(sorted(primary_labels.items())),
            "baseline_distribution_drift": distribution_drift if total_primary else None,
        }
    return result


def _primary_label(record: dict[str, Any]) -> str | None:
    """Return the highest-scoring known label for one benchmark record."""
    known = [item for item in record["classifications"] if item["status"] == "known"]
    if not known:
        return None
    return max(known, key=lambda item: (item["score"], item["name"]))["name"].casefold()


def _pairwise_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure per-email primary-label agreement between every model pair."""
    by_model: dict[str, dict[str, str | None]] = defaultdict(dict)
    for record in records:
        by_model[record["model"]][record["message_id"]] = (
            _primary_label(record) if record["error"] is None else None
        )

    models = sorted(by_model)
    result: dict[str, Any] = {}
    for index, left in enumerate(models):
        for right in models[index + 1 :]:
            shared = set(by_model[left]) & set(by_model[right])
            comparable = {
                message_id
                for message_id in shared
                if by_model[left][message_id] is not None
                and by_model[right][message_id] is not None
            }
            agreement = sum(
                by_model[left][message_id] == by_model[right][message_id]
                for message_id in comparable
            )
            key = f"{left} vs {right}"
            result[key] = {
                "messages": len(shared),
                "both_predicted": len(comparable),
                "missing_on_either": len(shared) - len(comparable),
                "agreement_count": agreement,
                "agreement": agreement / len(comparable) if comparable else None,
                "mismatch_count": len(comparable) - agreement,
            }
    return result


def main() -> None:
    """Run the requested model comparison and write private JSONL results."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("tests/fixtures/corpus/live.jsonl"),
    )
    parser.add_argument("--baseline", type=Path, default=Path("tests/fixtures/corpus/live.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/opencode/ollama-benchmark.jsonl"))
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("/tmp/opencode/ollama-benchmark-summary.json"),
    )
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--keep-alive", default="5m")
    parser.add_argument("--log-file", type=Path)
    parser.add_argument(
        "--records-in",
        type=Path,
        help="Re-summarize existing JSONL records without making model calls.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    parser.add_argument("--models", nargs="+", required=True)
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
        filename=str(args.log_file) if args.log_file else None,
    )
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    if not args.models:
        raise SystemExit("at least one model is required")

    messages = _read_corpus(args.corpus, args.limit)
    baseline = _read_baseline(args.baseline)
    categories = tuple(dict.fromkeys((*DEFAULT_CATEGORIES, *baseline.values())))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    if args.records_in is not None:
        records = [json.loads(line) for line in args.records_in.read_text().splitlines()]
    else:
        try:
            import litellm
        except ImportError as exc:
            raise SystemExit("LiteLLM is required; install spork[llm]") from exc
        litellm.set_verbose = False
        records = []
        for model in args.models:
            LOGGER.info("starting model=%s messages=%d", model, len(messages))
            for index, message in enumerate(messages, start=1):
                ps_before = _ps(args.api_base)
                classifications, tokens_in, tokens_out, error, latency_ms = _call_model(
                    litellm.completion,
                    model=model,
                    api_base=args.api_base,
                    message=message,
                    categories=categories,
                    max_tokens=args.max_tokens,
                    keep_alive=args.keep_alive,
                )
                ps_after = _ps(args.api_base)
                record = build_benchmark_record(
                    model=model,
                    message_id=message["message_id"],
                    subject=message["subject"],
                    classifications=classifications,
                    latency_ms=latency_ms,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error=error,
                    ps_before=ps_before,
                    ps_after=ps_after,
                    known_categories=frozenset(categories),
                    fingerprint=email_fingerprint(
                        message["from_address"], message["subject"], message["body_text"]
                    ),
                )
                records.append(record)
                LOGGER.info(
                    "model=%s index=%d/%d latency_ms=%.1f tokens_in=%s "
                    "tokens_out=%s error=%s ps_after=%s",
                    model,
                    index,
                    len(messages),
                    latency_ms,
                    tokens_in,
                    tokens_out,
                    error,
                    ps_after,
                )
    args.output.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records))
    summary = {
        "api_base": args.api_base,
        "messages": len(messages),
        "baseline_records": len(baseline),
        "models": _summary(records, baseline),
        "pairwise_agreement": _pairwise_summary(records),
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
