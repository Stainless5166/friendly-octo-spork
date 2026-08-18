"""Unit tests for accumulated classifications and policy decisions."""

from __future__ import annotations

import pytest

from spork.core.classify.decisions import (
    Classification,
    ClassificationPolicy,
    DestinationPolicy,
    decide_classifications,
    exact_duplicate_key,
    merge_classifications,
)
from spork.core.models import NormalizedMessage


def test_merge_classifications_keeps_greatest_score_for_each_name() -> None:
    merged = merge_classifications(
        [Classification(name="banking", score=100)],
        [Classification(name="banking", score=80), Classification(name="alert", score=80)],
    )

    assert merged == (
        Classification(name="alert", score=80),
        Classification(name="banking", score=100),
    )


def test_merge_classifications_applies_stage_threshold_before_accumulating() -> None:
    merged = merge_classifications(
        (),
        [Classification(name="security", score=20), Classification(name="alert", score=80)],
        minimum_score=50,
    )

    assert merged == (Classification(name="alert", score=80),)


def test_decide_classifications_selects_only_the_highest_eligible_mailbox() -> None:
    decision = decide_classifications(
        [Classification(name="banking", score=100), Classification(name="technology", score=90)],
        ClassificationPolicy(
            mailboxes={
                "banking": DestinationPolicy(destination="Banking and Finance", minimum_score=70),
                "technology": DestinationPolicy(destination="Technology", minimum_score=70),
            }
        ),
    )

    assert decision.mailbox == "Banking and Finance"
    assert decision.tags == ()


def test_decide_classifications_adds_all_eligible_tags_and_retains_evidence() -> None:
    classifications = (
        Classification(name="banking", score=100),
        Classification(name="alert", score=80),
        Classification(name="security", score=20),
    )
    decision = decide_classifications(
        classifications,
        ClassificationPolicy(
            mailboxes={
                "banking": DestinationPolicy(destination="Banking and Finance", minimum_score=70)
            },
            tags={
                "alert": DestinationPolicy(destination="Alert", minimum_score=70),
                "security": DestinationPolicy(destination="Security", minimum_score=50),
            },
        ),
    )

    assert decision.mailbox == "Banking and Finance"
    assert decision.tags == ("Alert",)
    assert decision.classifications == classifications


def test_decide_classifications_breaks_equal_mailbox_scores_by_name() -> None:
    decision = decide_classifications(
        [Classification(name="banking", score=80), Classification(name="technology", score=80)],
        ClassificationPolicy(
            mailboxes={
                "banking": DestinationPolicy(destination="Banking", minimum_score=70),
                "technology": DestinationPolicy(destination="Technology", minimum_score=70),
            }
        ),
    )

    assert decision.mailbox == "Technology"


def test_classification_rejects_scores_outside_the_public_scale() -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        Classification(name="security", score=101)


def test_exact_duplicate_key_ignores_case_and_whitespace_formatting() -> None:
    first = NormalizedMessage(
        message_id="one",
        thread_id="thread-one",
        from_address="alerts@example.com",
        from_domain="example.com",
        subject="Weekly report",
        body_text="Total: 10\nItems: 2",
    )
    second = NormalizedMessage(
        message_id="two",
        thread_id="thread-two",
        from_address="ALERTS@EXAMPLE.COM",
        from_domain="example.com",
        subject="  weekly   REPORT ",
        body_text="Total: 10 Items: 2",
    )

    assert exact_duplicate_key(first) == exact_duplicate_key(second)
