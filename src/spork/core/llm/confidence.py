"""Confidence-band gating (docs/DESIGN.md §10.3, §11).

Three bands from two config.toml thresholds: high confidence acts
silently, mid confidence acts and alerts, low confidence only alerts.
Pure function — no Verdict, config-loading, or state dependency, so
the daemon's action-vs-alert decision is unit-testable without any of
those.
"""

from __future__ import annotations

import math
from typing import Literal

ConfidenceBand = Literal["autoact", "autoact_alert", "alert_only"]


def confidence_band(
    confidence: float,
    *,
    alert_threshold: float,
    autoact_threshold: float,
) -> ConfidenceBand:
    """Classify `confidence` into one of §11's three action bands.

    Both thresholds are inclusive on their own side:
    `confidence >= autoact_threshold` -> `"autoact"`;
    `alert_threshold <= confidence < autoact_threshold` ->
    `"autoact_alert"`; anything lower -> `"alert_only"`.

    Raises `ValueError` if `alert_threshold > autoact_threshold` — a
    misconfigured `config.toml` (the "always alert" line set higher
    than the "never alert" line) rather than something to silently
    pick a band from. Also raises if any argument is NaN — found by
    CrossHair (verification/README.md), not by example or property
    testing: every NaN comparison is `False` under IEEE 754, so both
    `>=` checks below used to fall through silently to `"alert_only"`
    rather than raising. Never reachable via a real `Verdict`
    (§10.1's `Field(ge=0.0, le=1.0)` already rejects NaN before one
    can be constructed) but directly reachable via a hand-edited
    `config.toml` — TOML's float syntax accepts `nan`, and
    `TieringConfig.alert_threshold`/`autoact_threshold` carry no such
    constraint.
    """
    if math.isnan(confidence) or math.isnan(alert_threshold) or math.isnan(autoact_threshold):
        raise ValueError(
            f"confidence_band() got a NaN argument (confidence={confidence}, "
            f"alert_threshold={alert_threshold}, autoact_threshold={autoact_threshold}) — "
            f"check config.toml's [tiering] section and the Tier 2 verdict this came from"
        )

    if alert_threshold > autoact_threshold:
        raise ValueError(
            f"alert_threshold ({alert_threshold}) must not exceed "
            f"autoact_threshold ({autoact_threshold}) — check config.toml's "
            f"[tiering] section"
        )

    if confidence >= autoact_threshold:
        return "autoact"
    if confidence >= alert_threshold:
        return "autoact_alert"
    return "alert_only"
