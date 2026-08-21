"""Robustness (fuzz) tests for spork.core.llm.clean (docs/DESIGN.md §16.3).

A different fuzzing rationale than §16.1's decision-correctness
property tests: clean_body() parses raw email body text — content an
external sender fully controls, including malicious/malformed HTML —
so the risk here is clean_body() itself crashing or hanging and taking
an escalation down with it, not a wrong routing decision. These state
robustness invariants (never raises, output length is bounded, tag
markup never survives) over Hypothesis-generated bodies rather than
the hand-picked HTML/quote-chain examples test_clean.py/
test_clean_edge_cases.py already cover.
"""

from __future__ import annotations

from hypothesis import assume, given
from hypothesis import strategies as st

from spork.core.llm.clean import clean_body

# Printable-ish text, no control characters — clean_body() is meant for
# real (if hostile) email body text, not arbitrary byte soup.
_TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc")), max_size=200)

# A generated HTML tag's own name must be one HTMLParser actually
# recognizes as a tag (roughly [a-zA-Z][a-zA-Z0-9]*) for the "tags
# never survive" property below to mean anything — an unrecognized
# sequence just passes through as plain text, which isn't what's being
# tested here.
_TAG_NAME = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=8
)


@given(text=_TEXT, max_chars=st.integers(min_value=-50, max_value=300))
def test_clean_body_never_raises_for_any_generated_text_and_max_chars(
    text: str, max_chars: int
) -> None:
    """No generated body/max_chars combination — including a
    misconfigured negative max_chars, which pydantic's TieringConfig
    doesn't itself reject — ever raises. A crash here would take an
    in-flight Tier 2 escalation down with it."""
    result = clean_body(text, max_chars=max_chars)

    assert isinstance(result, str)


@given(text=_TEXT, max_chars=st.integers(min_value=0, max_value=300))
def test_clean_body_output_length_is_bounded_for_nonnegative_max_chars(
    text: str, max_chars: int
) -> None:
    """The final output is never longer than max_chars plus the fixed
    truncation marker — HTML stripping, quote-chain collapsing, and
    blank-line collapsing can only shrink text before truncation runs,
    and truncation itself is the only place length is bounded from
    below by construction, so this holds for any generated input."""
    result = clean_body(text, max_chars=max_chars)

    assert len(result) <= max_chars + len(" ... [truncated]")


@given(tag=_TAG_NAME, inner=st.text(alphabet=st.characters(blacklist_characters="<>"), max_size=50))
def test_clean_body_never_leaks_a_generated_html_tag_verbatim(tag: str, inner: str) -> None:
    """Any well-formed <tag>...</tag> pair Hypothesis generates is
    stripped down to its text content — not just the one hand-picked
    <p>/<b> example test_clean.py uses. max_chars is generous enough
    that truncation never interferes with this property."""
    raw = f"<{tag}>{inner}</{tag}>"

    cleaned = clean_body(raw, max_chars=10_000)

    assert f"<{tag}>" not in cleaned
    assert f"</{tag}>" not in cleaned


_PLAIN_WORD = st.text(alphabet=st.characters(categories=("L", "N")), max_size=10)
_PLAIN_TEXT = st.lists(_PLAIN_WORD, max_size=8).map(lambda words: " ".join(words))


@given(text=_PLAIN_TEXT)
def test_clean_body_is_idempotent_for_plain_text_with_room_to_spare(text: str) -> None:
    """Letters/digits/spaces only (no HTML, no quote markers, no
    newlines to collapse) with a generous max_chars: cleaning already-
    clean text a second time is a no-op, for any generated word list —
    applying clean_body() again should never keep transforming it."""
    assume("wrote:" not in text)  # the one pattern this alphabet could theoretically hit
    once = clean_body(text, max_chars=1000)

    twice = clean_body(once, max_chars=1000)

    assert once == twice
