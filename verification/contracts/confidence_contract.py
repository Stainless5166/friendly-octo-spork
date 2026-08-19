"""CrossHair contract for spork.core.llm.confidence.confidence_band()
(verification/README.md).

A thin wrapper, not a copy — imports and calls the real function, so
whatever CrossHair proves or disproves is a claim about the actual
`src/spork` code, not a stand-in. CrossHair reads `pre:`/`post:` lines
from the docstring (its own contract syntax, `_` meaning "the return
value") and symbolically explores every input satisfying `pre:` looking
for one that violates `post:` — not sampling, the way Hypothesis does.
"""

from __future__ import annotations

from spork.core.llm.confidence import ConfidenceBand, confidence_band


def confidence_band_is_autoact_iff_at_or_above_threshold(
    confidence: float, alert_threshold: float, autoact_threshold: float
) -> ConfidenceBand:
    """
    pre: alert_threshold <= autoact_threshold
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
    post: (_ == "alert_only") == (confidence < alert_threshold)
    """
    return confidence_band(
        confidence, alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
    )


def confidence_band_never_raises_for_a_valid_threshold_ordering(
    confidence: float, alert_threshold: float, autoact_threshold: float
) -> ConfidenceBand:
    """
    pre: alert_threshold <= autoact_threshold
    post: True
    """
    return confidence_band(
        confidence, alert_threshold=alert_threshold, autoact_threshold=autoact_threshold
    )
