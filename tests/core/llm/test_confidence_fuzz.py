"""Property-based tests for spork.core.llm.confidence (docs/DESIGN.md §16.1).

Companion to test_confidence.py/test_confidence_edge_cases.py's example-based
tests. confidence_band() is a pure three-way comparator ladder deciding
autoact-vs-alert on a live Tier 2 verdict — small enough that its whole
contract is cheap to state as properties over Hypothesis-generated
thresholds/confidences, rather than one example per boundary.
"""

from __future__ import annotations

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from spork.core.llm.confidence import confidence_band

# Bounded to a sane float range (not the full IEEE range) — confidence
# and thresholds are always Verdict.confidence-shaped values (§10.1's
# Field(ge=0.0, le=1.0)) or close to it; nothing in confidence_band()
# itself clamps to [0, 1], so a little headroom on both sides is kept
# to prove that's really true rather than assumed.
_FLOATS = st.floats(min_value=-1.0, max_value=2.0, allow_nan=False, allow_infinity=False)


@given(confidence=_FLOATS, alert_threshold=_FLOATS, autoact_threshold=_FLOATS)
def test_band_is_autoact_iff_confidence_at_or_above_autoact_threshold(
    confidence: float, alert_threshold: float, autoact_threshold: float
) -> None:
    """For any valid (non-inverted) threshold pair, "autoact" comes back
    exactly when confidence meets or exceeds autoact_threshold — never
    for a hair below it, never withheld for a hair above."""
    assume(alert_threshold <= autoact_threshold)

    band = confidence_band(
        confidence, alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
    )

    assert (band == "autoact") == (confidence >= autoact_threshold)


@given(confidence=_FLOATS, alert_threshold=_FLOATS, autoact_threshold=_FLOATS)
def test_band_is_alert_only_iff_confidence_below_alert_threshold(
    confidence: float, alert_threshold: float, autoact_threshold: float
) -> None:
    """ "alert_only" comes back exactly when confidence falls below
    alert_threshold — the only band with no action, so it must never be
    reachable at or above the "always at least alert-and-act" line."""
    assume(alert_threshold <= autoact_threshold)

    band = confidence_band(
        confidence, alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
    )

    assert (band == "alert_only") == (confidence < alert_threshold)


@given(confidence=_FLOATS, alert_threshold=_FLOATS, autoact_threshold=_FLOATS)
def test_band_is_always_exactly_one_of_the_three_literals(
    confidence: float, alert_threshold: float, autoact_threshold: float
) -> None:
    """No generated input ever produces a fourth outcome or raises for a
    reason other than inverted thresholds — the three bands are
    exhaustive for any valid threshold ordering."""
    assume(alert_threshold <= autoact_threshold)

    band = confidence_band(
        confidence, alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
    )

    assert band in ("autoact", "autoact_alert", "alert_only")


@given(confidence=_FLOATS, alert_threshold=_FLOATS, autoact_threshold=_FLOATS)
def test_inverted_thresholds_always_raise_value_error(
    confidence: float, alert_threshold: float, autoact_threshold: float
) -> None:
    """Any alert_threshold strictly above autoact_threshold is a
    misconfiguration, for every confidence Hypothesis generates — the
    guard fires on the thresholds alone, never on the confidence value
    that happens to accompany them."""
    assume(alert_threshold > autoact_threshold)

    with pytest.raises(ValueError, match="alert_threshold"):
        confidence_band(
            confidence, alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
        )


@given(
    alert_threshold=_FLOATS,
    autoact_threshold=_FLOATS,
    low=_FLOATS,
    high=_FLOATS,
)
def test_band_is_monotonic_non_decreasing_in_confidence(
    alert_threshold: float, autoact_threshold: float, low: float, high: float
) -> None:
    """A higher confidence never drops to a "less trusted" band than a
    lower one under the same thresholds — raising confidence can only
    move toward (never away from) autoact, for any generated pair."""
    assume(alert_threshold <= autoact_threshold)
    assume(low <= high)
    rank = {"alert_only": 0, "autoact_alert": 1, "autoact": 2}

    low_band = confidence_band(
        low, alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
    )
    high_band = confidence_band(
        high, alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
    )

    assert rank[low_band] <= rank[high_band]
