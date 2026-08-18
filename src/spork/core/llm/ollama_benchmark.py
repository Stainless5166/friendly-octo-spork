"""Safe structured-output helpers for the standalone Ollama benchmark."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any

from spork.core.classify.decisions import Classification, merge_classifications


def parse_classifications(raw: str) -> tuple[Classification, ...]:
    """Parse and validate one model's JSON classification response."""
    cleaned = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fenced is not None:
        cleaned = fenced.group(1)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model output was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("classifications"), list):
        raise ValueError("model JSON must contain a classifications list")

    incoming: list[Classification] = []
    for item in payload["classifications"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("each classification must contain a string name")
        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("each classification must contain a numeric score")
        incoming.append(Classification(name=item["name"], score=float(score)))
    return merge_classifications((), incoming)


def split_known_candidates(
    classifications: Sequence[Classification], known_categories: frozenset[str]
) -> tuple[tuple[Classification, ...], tuple[Classification, ...]]:
    """Separate action-eligible canonical labels from discovery candidates."""
    known = tuple(item for item in classifications if item.name.casefold() in known_categories)
    candidates = tuple(
        item for item in classifications if item.name.casefold() not in known_categories
    )
    return known, candidates


def email_fingerprint(from_address: str, subject: str, body_text: str) -> str:
    """Identify the same email across unlabeled and labeled private corpora."""

    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    material = "\x1f".join((normalize(from_address), normalize(subject), normalize(body_text)))
    return sha256(material.encode("utf-8")).hexdigest()


def build_benchmark_record(
    *,
    model: str,
    message_id: str,
    subject: str,
    classifications: Sequence[Classification],
    latency_ms: float,
    tokens_in: int | None,
    tokens_out: int | None,
    error: str | None,
    ps_before: Mapping[str, Any],
    ps_after: Mapping[str, Any],
    known_categories: frozenset[str],
    fingerprint: str,
) -> dict[str, Any]:
    """Build a non-content benchmark record with usage and Ollama load state."""
    del subject
    return {
        "model": model,
        "message_id": message_id,
        "fingerprint": fingerprint,
        "classifications": [
            {
                "name": item.name,
                "score": item.score,
                "status": "known" if item.name.casefold() in known_categories else "candidate",
            }
            for item in classifications
        ],
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "error": error,
        "ollama_ps_before": dict(ps_before),
        "ollama_ps_after": dict(ps_after),
    }
