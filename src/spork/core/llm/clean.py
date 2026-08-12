"""Body cleaning for Tier 2 prompts (docs/DESIGN.md §10).

Reduces a raw message body to the truncated, cleaned plaintext a Tier 2
prompt actually needs: HTML stripped, quoted-reply chains collapsed,
truncated to a bounded length. Kept as pure string transformation with
no message/JMAP knowledge, so it's testable without any of the
NormalizedMessage/pipeline machinery around it — and reusable if a
future caller (e.g. a preview in `spork rules test`) wants cleaned
body text without pulling in the LLM client.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

# Lines that mark the start of a quoted prior message — whichever
# pattern's earliest match comes first in the body wins; everything
# from that line onward is dropped. Patterns cover the common mail
# clients actually produce, not an exhaustive MIME-quoting grammar.
_QUOTE_MARKERS = (
    re.compile(r"^>", re.MULTILINE),  # bare '>'-prefixed quoted line
    re.compile(r"^On .{0,120}wrote:\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^-{3,}\s*Original Message\s*-{3,}", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^_{10,}\s*$", re.MULTILINE),  # Outlook-style separator line
)

# 3+ consecutive newlines (2+ blank lines) collapse to one blank line —
# HTML-sourced bodies routinely produce runs of these once tags are
# stripped out from between block-level elements.
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


class _TagStripper(HTMLParser):
    """Collects only the text content of an HTML document, tags dropped.

    A hand-rolled `HTMLParser` subclass rather than a new dependency
    (e.g. BeautifulSoup) — matches this project's preference for
    zero-dependency heuristics where the stdlib genuinely suffices
    (see `spork.core.classify`'s planned default backend).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def _strip_html(text: str) -> str:
    """Return `text` with any HTML markup reduced to its text content.

    Plain text with no tags at all passes through byte-for-byte —
    `HTMLParser` only ever removes what it recognizes as markup.
    """
    stripper = _TagStripper()
    stripper.feed(text)
    return stripper.get_text()


def _collapse_quote_chain(text: str) -> str:
    """Cut `text` at the earliest quoted-prior-message marker, if any.

    Reply chains grow every round trip; the quoted portion is old
    content the model has no need to re-read (and would otherwise
    inflate every escalated message's prompt for no benefit).
    """
    earliest: int | None = None
    for pattern in _QUOTE_MARKERS:
        match = pattern.search(text)
        if match is not None and (earliest is None or match.start() < earliest):
            earliest = match.start()
    return text if earliest is None else text[:earliest]


def _truncate(text: str, max_chars: int) -> str:
    """Truncate `text` to at most `max_chars`, marking that it happened.

    Cuts on a word boundary rather than mid-word, and always appends a
    marker — a silently truncated body reads to the LLM (and to a
    human debugging a verdict) as a complete message that just happens
    to stop abruptly, which is worse than an explicit "this was cut."
    """
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0]
    return f"{truncated} ... [truncated]"


def clean_body(body_text: str, *, max_chars: int = 4000) -> str:
    """Clean a raw message body for inclusion in a Tier 2 prompt.

    Order matters: HTML is stripped first (so quote-marker regexes see
    plain text, not markup), then the quote chain is collapsed (so
    truncation isn't spent budget on content already dropped), then
    the result is truncated and whitespace-normalized.
    """
    text = _strip_html(body_text)
    text = _collapse_quote_chain(text)
    text = _truncate(text, max_chars)
    text = _EXCESS_BLANK_LINES.sub("\n\n", text)
    return text.strip()
