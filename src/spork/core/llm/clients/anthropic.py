"""Anthropic Claude adapter for LLMClient (docs/DESIGN.md §10.1, §10).

`get_verdict()` is deliberately unimplemented: doing it for real means
an actual `anthropic` SDK call against the live Claude API, which this
environment can't exercise honestly. Rather than leaving the class's
shape unspecified until that becomes possible, it's settled now —
constructor args, method name/signature — and raises a clear,
catchable `NotImplementedError` in the meantime (docs/ROADMAP.md M3),
same treatment as `JmapClient`'s `connect()`/`fetch_new_messages()`/
`apply_action()` (docs/DESIGN.md §9.3). No `anthropic` import here:
the SDK isn't a dependency until there's a real call to make with it.
"""

from __future__ import annotations

from spork.core.llm.base import Verdict, VerdictRequest


class AnthropicLLMClient:
    """One Tier 2 backend: Claude, called via the `anthropic` SDK.

    `api_key`/`model`/`max_tokens` are stored but not used yet — real
    `anthropic` integration is where they'd actually be consumed.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "claude-sonnet-5",
        max_tokens: int = 1024,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens

    def get_verdict(self, request: VerdictRequest) -> Verdict:
        """Call Claude with `request` and return a validated Verdict."""
        raise NotImplementedError(
            "AnthropicLLMClient.get_verdict() requires a live Anthropic API "
            "session — not implemented yet, see docs/ROADMAP.md M3"
        )
