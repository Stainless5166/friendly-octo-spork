"""Acceptance tests for body cleaning (docs/DESIGN.md §10).

Pure string transformation, no NormalizedMessage/pipeline knowledge —
reduces a raw message body to the truncated, cleaned plaintext a Tier 2
prompt actually needs: HTML stripped, quoted-reply chains collapsed,
truncated to a bounded length.
"""

from __future__ import annotations

from spork.core.llm.clean import clean_body


def test_clean_body_strips_html_tags() -> None:
    """HTML markup is stripped down to its text content."""
    raw = "<p>Hello <b>there</b>,</p><p>Can we meet Friday?</p>"

    cleaned = clean_body(raw)

    assert "<" not in cleaned
    assert "Hello there" in cleaned
    assert "Can we meet Friday?" in cleaned


def test_clean_body_collapses_a_quote_chain_introduced_by_wrote_line() -> None:
    """A classic "On ... wrote:" reply header and everything after it
    (the quoted prior message) is dropped — only the new content above
    it is Tier 2 prompt material."""
    raw = (
        "Sure, Friday works for me.\n\n"
        "On Tue, Jan 6, 2026 at 3:00 PM Alice <alice@example.com> wrote:\n"
        "> Can we meet Friday?\n"
        "> Let me know.\n"
    )

    cleaned = clean_body(raw)

    assert "Sure, Friday works for me." in cleaned
    assert "wrote:" not in cleaned
    assert "Can we meet Friday?" not in cleaned


def test_clean_body_collapses_a_quote_chain_introduced_by_gt_prefixed_lines() -> None:
    """A body that goes straight into '>'-prefixed quoted lines (no
    "wrote:" header) still has the quoted portion dropped."""
    raw = "Sounds good.\n\n> original message\n> more original message\n"

    cleaned = clean_body(raw)

    assert "Sounds good." in cleaned
    assert "original message" not in cleaned


def test_clean_body_truncates_long_bodies() -> None:
    """A body longer than max_chars is truncated, not sent to the LLM
    in full — §10's cost-control rationale."""
    raw = "word " * 2000  # far longer than any reasonable max_chars

    cleaned = clean_body(raw, max_chars=100)

    assert len(cleaned) <= 120  # some slack for a truncation marker
    assert "truncated" in cleaned.lower()


def test_clean_body_leaves_a_short_plain_body_unchanged_in_substance() -> None:
    """A short, already-plain, unquoted body passes through with its
    content intact (whitespace normalization aside) — cleaning doesn't
    mangle the common case."""
    raw = "Thanks for the update, talk soon."

    cleaned = clean_body(raw)

    assert cleaned.strip() == raw


def test_clean_body_normalizes_excess_blank_lines() -> None:
    """HTML-sourced bodies often produce runs of blank lines after tag
    stripping; those collapse down rather than bloating the prompt."""
    raw = "<p>Paragraph one.</p>\n\n\n\n\n<p>Paragraph two.</p>"

    cleaned = clean_body(raw)

    assert "\n\n\n" not in cleaned
