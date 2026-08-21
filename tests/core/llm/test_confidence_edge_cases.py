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


def test_nan_confidence_raises_value_error_instead_of_silently_alert_only() -> None:
    """FOUND BY CROSSHAIR (verification/README.md), not by example or
    property testing: every NaN comparison is False under IEEE 754, so
    both `>=` checks used to fall through silently to "alert_only" for
    a NaN confidence -- never reachable via a real Verdict (pydantic's
    Field(ge=0.0, le=1.0) already rejects NaN before one can be
    constructed) but directly reachable via a hand-edited config.toml,
    since TOML's own float syntax accepts `nan` and TieringConfig's
    alert_threshold/autoact_threshold carry no such constraint."""
    with pytest.raises(ValueError, match="NaN"):
        confidence_band(float("nan"), alert_threshold=0.55, autoact_threshold=0.85)


def test_nan_alert_threshold_raises_value_error() -> None:
    """Same guard, the other reachable path: a hand-edited config.toml
    with alert_threshold = nan."""
    with pytest.raises(ValueError, match="NaN"):
        confidence_band(0.7, alert_threshold=float("nan"), autoact_threshold=0.85)


def test_nan_autoact_threshold_raises_value_error() -> None:
    with pytest.raises(ValueError, match="NaN"):
        confidence_band(0.7, alert_threshold=0.55, autoact_threshold=float("nan"))
