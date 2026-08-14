"""RecordedLLMClient: replays pre-recorded Verdicts (docs/DESIGN.md §10.5).

The LLMClient equivalent of `spork.core.providers.file.FileProvider`
(§9.3): a second, fully real adapter with no `NotImplementedError`
anywhere, for CI and offline dry-runs — `LiteLLMClient` can't be
exercised in CI (no live API key, and even with one a real call is
slow, costs money, and isn't deterministic). Not a way to fake a live
verdict for production use — same caveat `FileProvider` states for
messages.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from spork.core.llm.base import LLMCallUsage, LLMResult, Verdict, VerdictRequest


class RecordedResponsesLoadError(ValueError):
    """Raised when a recorded-responses JSON file can't be parsed into Verdicts.

    Covers a missing file, malformed JSON, a non-object top level, and
    an entry that fails Verdict's own validation — one catchable type,
    same fail-loud pattern as `MessagesLoadError`.
    """


class UnrecordedResponseError(KeyError):
    """Raised when a VerdictRequest has no matching recorded response.

    Names the subjects that *were* recorded — same "name what's
    available" shape as `UnknownBranchError` (§9.4).
    """


def load_recorded_responses(path: str | Path) -> dict[str, Verdict]:
    """Parse a JSON object of {subject: verdict-shaped-object} into
    Verdicts, keyed by subject.

    Fails fast on a malformed fixture file — called once at
    `RecordedLLMClient` construction, not lazily on the first
    `get_verdict()` call.
    """
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise RecordedResponsesLoadError(f"responses file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RecordedResponsesLoadError(f"invalid JSON in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise RecordedResponsesLoadError(
            f"{path} must contain a JSON object keyed by subject, got {type(raw).__name__}"
        )

    responses: dict[str, Verdict] = {}
    for subject, entry in raw.items():
        try:
            responses[subject] = Verdict.model_validate(entry)
        except ValidationError as exc:
            raise RecordedResponsesLoadError(
                f"{path}: recorded response for {subject!r} is not a valid Verdict: {exc}"
            ) from exc

    return responses


class RecordedLLMClient:
    """Replays a fixed set of pre-recorded Verdicts, keyed by
    `VerdictRequest.subject` — chosen over a hash of the full request
    so a human reading the fixture file can immediately tell which
    recorded email each entry is for.
    """

    def __init__(self, responses_path: str | Path) -> None:
        self._responses = load_recorded_responses(responses_path)

    def get_verdict(self, request: VerdictRequest) -> LLMResult:
        try:
            verdict = self._responses[request.subject]
        except KeyError as exc:
            raise UnrecordedResponseError(
                f"no recorded response for subject {request.subject!r}; "
                f"known subjects: {sorted(self._responses)}"
            ) from exc
        return LLMResult(verdict=verdict, usage=LLMCallUsage(tokens_in=0, tokens_out=0))
