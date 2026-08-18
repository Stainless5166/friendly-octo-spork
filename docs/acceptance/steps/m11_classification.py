"""Behave bindings for the local classification decision model (M11)."""

from __future__ import annotations

from typing import Any

from behave import given, then, when

from spork.core.classify.decisions import (
    Classification,
    ClassificationPolicy,
    DestinationPolicy,
    decide_classifications,
    merge_classifications,
)


def _classification(context: Any, name: str) -> Classification:
    """Return one named evidence item from the scenario accumulator."""
    return next(item for item in context.classifications if item.name == name)


@given("a message has no classifications")
def no_classifications(context: Any) -> None:
    """Start a fresh evidence list for the merge scenario."""
    context.classifications = ()


@when('the sender-domain stage adds "{name}" with score {score:d}')
@when('the keyword stage adds "{name}" with score {score:d}')
def add_classification(context: Any, name: str, score: int) -> None:
    """Merge one stage's contribution using the production accumulator."""
    context.classifications = merge_classifications(
        context.classifications, (Classification(name=name, score=score),)
    )


@then('the classifications contain "{name}" with score {score:d}')
def classification_has_score(context: Any, name: str, score: int) -> None:
    """Verify the merged maximum score for one classification."""
    assert _classification(context, name).score == score


@then('"{name}" appears only once')
def classification_is_unique(context: Any, name: str) -> None:
    """Verify duplicate evidence names were collapsed."""
    assert sum(item.name == name for item in context.classifications) == 1


@given(
    'the classifications are "{first_name}" {first_score:d}, '
    '"{second_name}" {second_score:d}, and "{third_name}" {third_score:d}'
)
def three_classifications(
    context: Any,
    first_name: str,
    first_score: int,
    second_name: str,
    second_score: int,
    third_name: str,
    third_score: int,
) -> None:
    """Parse the three-item Gherkin evidence list into model objects."""
    values = [
        (first_name, first_score),
        (second_name, second_score),
        (third_name, third_score),
    ]
    context.classifications = tuple(
        Classification(name=name, score=score) for name, score in values
    )


@given('the classifications are "{name}" {score:d}')
def one_classification(context: Any, name: str, score: int) -> None:
    """Parse the single-item Gherkin evidence list into model objects."""
    context.classifications = (Classification(name=name, score=score),)


@given('the mailbox threshold for "{name}" is {score:d}')
def mailbox_threshold(context: Any, name: str, score: int) -> None:
    """Store one mailbox policy from the scenario."""
    context.mailbox_policies = getattr(context, "mailbox_policies", {})
    context.mailbox_policies[name] = DestinationPolicy(
        destination="Banking and Finance" if name == "banking" else name.title(),
        minimum_score=score,
    )


@given('the tag threshold for "{name}" is {score:d}')
def tag_threshold(context: Any, name: str, score: int) -> None:
    """Store one additive tag policy from the scenario."""
    context.tag_policies = getattr(context, "tag_policies", {})
    context.tag_policies[name] = DestinationPolicy(destination=name.title(), minimum_score=score)


@when("the decider evaluates the classifications")
def evaluate_classifications(context: Any) -> None:
    """Run the production decision function against scenario policy."""
    context.decision = decide_classifications(
        context.classifications,
        ClassificationPolicy(
            mailboxes=getattr(context, "mailbox_policies", {}),
            tags=getattr(context, "tag_policies", {}),
        ),
    )


@then('the selected mailbox is "{mailbox}"')
def selected_mailbox(context: Any, mailbox: str) -> None:
    """Verify the one primary mailbox decision."""
    assert context.decision.mailbox == mailbox


@then("no mailbox is selected")
def no_mailbox(context: Any) -> None:
    """Verify that no mailbox crossed its policy threshold."""
    assert context.decision.mailbox is None


@then('the selected tags contain only "{tag}"')
def selected_tags_only(context: Any, tag: str) -> None:
    """Verify additive tag selection and threshold filtering."""
    assert context.decision.tags == (tag,)


@then("no tags are selected")
def no_tags(context: Any) -> None:
    """Verify that no tag crossed its policy threshold."""
    assert context.decision.tags == ()


@then("the classification evidence is retained")
def evidence_retained(context: Any) -> None:
    """Verify low-confidence evidence remains available after deciding."""
    assert context.decision.classifications == context.classifications
