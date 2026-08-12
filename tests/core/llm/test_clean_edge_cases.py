"""Failure/edge-case tests for clean_body().

Companion to test_clean.py's acceptance tests.
"""

from __future__ import annotations

from spork.core.llm.clean import clean_body


def test_clean_body_handles_an_empty_string() -> None:
    """An empty body is a legitimate input, not an error."""
    assert clean_body("") == ""


def test_clean_body_decodes_html_entities() -> None:
    """HTML entities in the source decode to their real characters,
    not the literal escape sequence."""
    cleaned = clean_body("<p>Fish &amp; chips &mdash; 5pm?</p>")

    assert "&amp;" not in cleaned
    assert "Fish & chips" in cleaned


def test_clean_body_uses_the_earliest_quote_marker_when_several_are_present() -> None:
    """When more than one quote-marker pattern appears, the body is cut
    at whichever occurs first — a later, redundant marker doesn't leak
    extra quoted content through."""
    raw = (
        "New content here.\n\n"
        "On Tue, Jan 6, 2026 at 3:00 PM Alice wrote:\n"
        "> Quoted line one\n"
        "-----Original Message-----\n"
        "Even older content\n"
    )

    cleaned = clean_body(raw)

    assert "New content here." in cleaned
    assert "wrote:" not in cleaned
    assert "Quoted line one" not in cleaned
    assert "Even older content" not in cleaned


def test_clean_body_does_not_add_a_truncation_marker_at_exactly_max_chars() -> None:
    """A body exactly at the length limit is not truncated — the limit
    is inclusive, not an off-by-one trap."""
    raw = "a" * 100

    cleaned = clean_body(raw, max_chars=100)

    assert cleaned == raw
    assert "truncated" not in cleaned.lower()


def test_clean_body_truncates_a_single_long_word_with_no_space_to_break_on() -> None:
    """A pathological single unbroken "word" longer than max_chars still
    truncates cleanly instead of crashing on the word-boundary split."""
    raw = "a" * 500

    cleaned = clean_body(raw, max_chars=50)

    assert "truncated" in cleaned.lower()
    assert len(cleaned) < len(raw)
