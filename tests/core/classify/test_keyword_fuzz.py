"""Property-based tests for KeywordClassifier (docs/DESIGN.md §16.1).

Companion to test_keyword.py/test_keyword_edge_cases.py's example-based
tests. classify()'s scoring (a match fraction) and tie-break (first
listed wins) are stated as invariants over Hypothesis-generated category
keyword maps and messages, rather than the shipped default vocabulary
alone.
"""

from __future__ import annotations

from hypothesis import assume, given
from hypothesis import strategies as st

from spork.core.classify.keyword import DEFAULT_CATEGORY, KeywordClassifier
from spork.core.models import NormalizedMessage

# Distinct single-token "words" — real substring matching only, no
# punctuation/whitespace inside a token, so a generated haystack built
# by joining tokens can't accidentally fuse two of them into a false
# match. unique=True at each call site keeps categories/keywords from
# colliding with each other.
_WORD = st.text(alphabet=st.characters(categories=("L", "N")), min_size=3, max_size=8)

# A category's keyword list, 0-4 words long — deliberately variable
# length so the match-fraction scoring (matched / len(keywords)) is
# actually exercised, not just the always-1-keyword case.
_KEYWORDS = st.lists(_WORD, max_size=4).map(tuple)


@st.composite
def _messages(draw: st.DrawFn) -> NormalizedMessage:
    """An arbitrary NormalizedMessage varying only subject/body_text —
    the only two fields classify() reads."""
    return NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address="someone@example.com",
        from_domain="example.com",
        subject=draw(st.text(max_size=20)),
        body_text=draw(st.text(max_size=40)),
    )


@given(message=_messages(), category_keywords=st.dictionaries(_WORD, _KEYWORDS, max_size=6))
def test_every_score_is_between_zero_and_one(
    message: NormalizedMessage, category_keywords: dict[str, tuple[str]]
) -> None:
    """A match fraction can never fall outside [0, 1], for any generated
    category/keyword/message combination — matched count is always
    between 0 and the category's own keyword count."""
    result = KeywordClassifier(category_keywords=category_keywords).classify(message)

    assert all(0.0 <= score <= 1.0 for score in result.scores.values())


@given(message=_messages(), category_keywords=st.dictionaries(_WORD, _KEYWORDS, max_size=6))
def test_winning_category_always_has_the_maximum_score(
    message: NormalizedMessage, category_keywords: dict[str, tuple[str]]
) -> None:
    """The returned category is never one some other category's score
    beats — true whether it won on real matches or fell back to
    default_category (every score tied at 0.0)."""
    classifier = KeywordClassifier(category_keywords=category_keywords)

    result = classifier.classify(message)

    if result.category == DEFAULT_CATEGORY and DEFAULT_CATEGORY not in category_keywords:
        assert all(score == 0.0 for score in result.scores.values())
    else:
        assert result.scores[result.category] == max(result.scores.values())


@given(category=_WORD, keyword=_WORD, other_category=_WORD)
def test_a_category_with_no_keywords_never_wins_against_a_matching_one(
    category: str, keyword: str, other_category: str
) -> None:
    """An empty keyword tuple always scores exactly 0.0 (never a
    division error, never a phantom match) and so never beats a
    category whose one keyword is actually present."""
    assume(category != other_category)
    message = NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address="someone@example.com",
        from_domain="example.com",
        subject=keyword,
        body_text="",
    )
    classifier = KeywordClassifier(category_keywords={category: (), other_category: (keyword,)})

    result = classifier.classify(message)

    assert result.scores[category] == 0.0
    assert result.category == other_category


@given(categories=st.lists(_WORD, min_size=2, max_size=5, unique=True), keyword=_WORD)
def test_tie_break_always_goes_to_the_first_listed_category(
    categories: list[str], keyword: str
) -> None:
    """When every category's single keyword is present (every score
    tied at 1.0), the winner is always whichever category was listed
    first — for any generated category ordering, not one hand-picked
    pair."""
    message = NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address="someone@example.com",
        from_domain="example.com",
        subject=keyword,
        body_text="",
    )
    classifier = KeywordClassifier(category_keywords={cat: (keyword,) for cat in categories})

    result = classifier.classify(message)

    assert result.category == categories[0]


@given(message=_messages(), category_keywords=st.dictionaries(_WORD, _KEYWORDS, max_size=6))
def test_classify_never_raises_for_any_generated_message_or_vocabulary(
    message: NormalizedMessage, category_keywords: dict[str, tuple[str]]
) -> None:
    """Robustness invariant: whatever subject/body_text/keyword map
    Hypothesis generates, classify() always returns rather than
    raising — there's no input shape that should crash Tier 1."""
    KeywordClassifier(category_keywords=category_keywords).classify(message)
