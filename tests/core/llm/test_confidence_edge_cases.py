"""Failure/edge-case tests for spork.core.llm.confidence.

Companion to test_confidence.py's acceptance tests.
"""

from __future__ import annotations

import pytest

from spork.core.llm.confidence import confidence_band


def test_misconfigured_thresholds_raise_value_error() -> None:
    """alert_threshold higher than autoact_threshold (the "always
    alert" line set above the "never alert" line) is a config
    mistake — fails loudly rather than silently picking whichever band
    the broken comparison happens to land on."""
    with pytest.raises(ValueError, match="alert_threshold"):
        confidence_band(0.7, alert_threshold=0.9, autoact_threshold=0.5)


def test_equal_thresholds_never_produce_autoact_alert() -> None:
    """EDGE CASE FOUND WHILE TESTING: a valid-but-degenerate config
    (alert_threshold == autoact_threshold, not rejected — only `>` is
    a config mistake, `==` is a legitimate "no middle band" choice)
    makes "autoact_alert" unreachable: confidence >= the shared
    threshold is always "autoact" (checked first), and anything below
    it is always "alert_only". Not a bug — the two checks are correct,
    inclusive on their own side, exactly as documented — but worth
    locking in explicitly so a future reader doesn't mistake "this
    config never alerts-and-acts" for a bug in confidence_band()
    itself."""
    assert confidence_band(0.7, alert_threshold=0.7, autoact_threshold=0.7) == "autoact"
    assert confidence_band(0.6999, alert_threshold=0.7, autoact_threshold=0.7) == "alert_only"


def test_confidence_of_exactly_zero_and_one_are_handled() -> None:
    """The extremes of Verdict.confidence's valid range (§10.1's
    Field(ge=0.0, le=1.0)) both classify without error."""
    assert confidence_band(0.0, alert_threshold=0.55, autoact_threshold=0.85) == "alert_only"
    assert confidence_band(1.0, alert_threshold=0.55, autoact_threshold=0.85) == "autoact"
