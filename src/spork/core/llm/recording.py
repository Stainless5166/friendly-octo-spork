"""Append exact successful LLM calls to a private acceptance corpus (§10.1)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from spork.core.llm.base import LLMClient, LLMResult, VerdictRequest
from spork.core.llm.prompt import CompletionPrompt, build_prompt


def _utc_now_iso() -> str:
    """Use an injected clock in tests while recording real UTC timestamps by default."""
    return datetime.now(UTC).isoformat()


def _prompt_payload(prompt: CompletionPrompt) -> dict[str, object]:
    """Produce the stable JSON shape shared by hashing and corpus output."""
    return {
        "messages": list(prompt.messages),
        "tools": list(prompt.tools),
        "tool_choice": prompt.tool_choice,
    }


def prompt_sha256(prompt: CompletionPrompt) -> str:
    """Identify exact prompts without using message subjects as uniqueness keys."""
    canonical = json.dumps(
        _prompt_payload(prompt), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class RecordingLLMClient:
    """Decorate any LLMClient and append successful calls as JSON Lines."""

    def __init__(
        self,
        client: LLMClient,
        *,
        corpus_path: str | Path = "tests/fixtures/corpus/live.jsonl",
        now: Callable[[], str] = _utc_now_iso,
    ) -> None:
        self._client = client
        self._corpus_path = Path(corpus_path)
        self._now = now

    def get_verdict(self, request: VerdictRequest) -> LLMResult:
        """Delegate first, then record only a successful validated result."""
        result = self._client.get_verdict(request)
        prompt = build_prompt(request)
        entry = {
            "subject": request.subject,
            "prompt": _prompt_payload(prompt),
            "prompt_sha256": prompt_sha256(prompt),
            "verdict": result.verdict.model_dump(mode="json"),
            "usage": {
                "tokens_in": result.usage.tokens_in,
                "tokens_out": result.usage.tokens_out,
            },
            "recorded_at": self._now(),
        }
        self._corpus_path.parent.mkdir(parents=True, exist_ok=True)
        with self._corpus_path.open("a", encoding="utf-8") as corpus:
            corpus.write(json.dumps(entry, sort_keys=True) + "\n")
        return result
