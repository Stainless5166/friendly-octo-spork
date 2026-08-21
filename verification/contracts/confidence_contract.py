"""CrossHair contract for spork.core.llm.confidence.confidence_band()
(verification/README.md).

A thin wrapper, not a copy — imports and calls the real function, so
whatever CrossHair proves or disproves is a claim about the actual
`src/spork` code, not a stand-in. CrossHair reads `pre:`/`post:` lines
from the docstring (its own contract syntax, `_` meaning "the return
value") and symbolically explores every input satisfying `pre:` looking
for one that violates `post:` — not sampling, the way Hypothesis does.

Preconditions below exclude NaN via `x == x` (`False` iff `x` is NaN,
under IEEE 754) rather than `math.isnan(x)` — a helper-function or
`math` call turned out to make CrossHair's search meaningfully less
conclusive here (checked: with `math.isnan`, two of the four properties
below came back "not confirmed" instead of "confirmed over all paths",
even with an increased --per_condition_timeout; the plain self-equality
form confirms all three non-NaN properties instead). confidence_band()
now raises ValueError on a NaN argument (the real gap this file's first
run found; see verification/README.md) — that behavior gets its own
three contracts below, one per argument (rather than one combined
`pre:` disjunction, which doesn't fit the line-length limit).
"""

from __future__ import annotations

from spork.core.llm.confidence import ConfidenceBand, confidence_band


def confidence_band_is_autoact_iff_at_or_above_threshold(
    confidence: float, alert_threshold: float, autoact_threshold: float
) -> ConfidenceBand:
    """
    pre: alert_threshold <= autoact_threshold
    pre: confidence == confidence
    pre: alert_threshold == alert_threshold
    pre: autoact_threshold == autoact_threshold
    post: (_ == "autoact") == (confidence >= autoact_threshold)
    """
    return confidence_band(
        confidence, alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
    )


def confidence_band_is_alert_only_iff_below_alert_threshold(
    confidence: float, alert_threshold: float, autoact_threshold: float
) -> ConfidenceBand:
    """
    pre: alert_threshold <= autoact_threshold
    pre: confidence == confidence
    pre: alert_threshold == alert_threshold
    pre: autoact_threshold == autoact_threshold
    post: (_ == "alert_only") == (confidence < alert_threshold)
    """
    return confidence_band(
        confidence, alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
    )


def confidence_band_never_raises_for_a_valid_nonnan_threshold_ordering(
    confidence: float, alert_threshold: float, autoact_threshold: float
) -> ConfidenceBand:
    """
    pre: alert_threshold <= autoact_threshold
    pre: confidence == confidence
    pre: alert_threshold == alert_threshold
    pre: autoact_threshold == autoact_threshold
    post: True
    """
    return confidence_band(
        confidence, alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
    )


def confidence_band_raises_on_nan_confidence(
    alert_threshold: float, autoact_threshold: float
) -> ConfidenceBand:
    """
    raises: ValueError
    """
    return confidence_band(
        float("nan"), alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
    )


def confidence_band_raises_on_nan_alert_threshold(
    confidence: float, autoact_threshold: float
) -> ConfidenceBand:
    """
    raises: ValueError
    """
    return confidence_band(
        confidence, alert_threshold=float("nan"), autoact_threshold=autoact_threshold
    )


def confidence_band_raises_on_nan_autoact_threshold(
    confidence: float, alert_threshold: float
) -> ConfidenceBand:
    """
    raises: ValueError
    """
    return confidence_band(
        confidence, alert_threshold=alert_threshold, autoact_threshold=float("nan")
    )
