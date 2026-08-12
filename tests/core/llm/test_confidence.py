"""Acceptance tests for spork.core.llm.confidence (docs/DESIGN.md §10.3).

confidence_band() is pure: a function of (confidence, alert_threshold,
autoact_threshold), no Verdict/config/state dependency.
"""

from __future__ import annotations

from spork.core.llm.confidence import confidence_band


def test_confidence_above_autoact_threshold_is_autoact() -> None:
    """High confidence acts silently — no alert."""
    band = confidence_band(0.9, alert_threshold=0.55, autoact_threshold=0.85)

    assert band == "autoact"


def test_confidence_between_thresholds_is_autoact_alert() -> None:
    """Middle-band confidence acts, but the action is also alerted —
    a human can review after the fact."""
    band = confidence_band(0.7, alert_threshold=0.55, autoact_threshold=0.85)

    assert band == "autoact_alert"


def test_confidence_below_alert_threshold_is_alert_only() -> None:
    """Low confidence never acts — alert only, no action taken."""
    band = confidence_band(0.3, alert_threshold=0.55, autoact_threshold=0.85)

    assert band == "alert_only"


def test_confidence_at_autoact_threshold_is_autoact() -> None:
    """The autoact threshold is inclusive on its own side — meeting it
    exactly is enough to autoact, not just exceeding it."""
    band = confidence_band(0.85, alert_threshold=0.55, autoact_threshold=0.85)

    assert band == "autoact"


def test_confidence_at_alert_threshold_is_autoact_alert() -> None:
    """The alert threshold is inclusive on its own side too — meeting
    it exactly still acts (with an alert), it doesn't drop to
    alert_only."""
    band = confidence_band(0.55, alert_threshold=0.55, autoact_threshold=0.85)

    assert band == "autoact_alert"
