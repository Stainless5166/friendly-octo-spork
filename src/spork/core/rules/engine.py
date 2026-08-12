"""Tier 1 rule evaluation (docs/DESIGN.md §9): first enabled match wins.

Deliberately the only place in spork that knows how to interpret a
`Condition` — the rule *schema* (schema.py) just declares what fields
exist, this module decides what they mean. Keeping that split means
`rules.toml` can be validated/parsed without importing evaluation
logic at all (useful for `spork rules test`'s dry-run path).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from spork.core.classify.base import ClassificationResult, TextClassifier
from spork.core.models import NormalizedMessage
from spork.core.rules.schema import Action, Condition, Rule


@dataclass(frozen=True, slots=True)
class RuleVerdict:
    """Result of running one message through the Tier 1 rule engine.

    Carries which rule (if any) produced the action so callers can log
    *why* something happened (docs/DESIGN.md §11's audit trail)
    without re-deriving it. `matched_rule_id is None` unambiguously
    means "fell through to the default policy", never "matched a rule
    with a blank id" — `Rule.id` is required, so that value is
    otherwise unreachable.
    """

    action: Action
    matched_rule_id: str | None


def _condition_matches(
    condition: Condition,
    message: NormalizedMessage,
    classify: Callable[[], ClassificationResult],
) -> bool:
    """Evaluate a single rule's `when` clause against `message`.

    AND semantics across whichever fields are set, rather than OR —
    in practice a `Condition` sets exactly one field (schema.py), but
    a future multi-field condition should have to opt into "any of
    these" rather than get it by accident. A condition with *no*
    fields set matches nothing, not everything: an all-default
    `Condition` is far more likely a bug in a hand-edited rules.toml
    than an intentional catch-all (`always: true` exists for that).
    """
    checked_any = False

    if condition.always:
        return True

    if condition.from_domain_in is not None:
        checked_any = True
        if message.from_domain not in condition.from_domain_in:
            return False

    if condition.from_in is not None:
        checked_any = True
        if message.from_address not in condition.from_in:
            return False

    if condition.local_classifier_category_in is not None:
        checked_any = True
        if classify().category not in condition.local_classifier_category_in:
            return False

    return checked_any


def evaluate(
    message: NormalizedMessage,
    rules: Sequence[Rule],
    *,
    default_unmatched_action: Action,
    classifier: TextClassifier | None = None,
) -> RuleVerdict:
    """Run `message` through `rules` in order; the first enabled match wins.

    `classifier` is optional and evaluated lazily, at most once per
    call: nothing here invokes it until some rule's condition actually
    needs its output, so a `rules.toml` that never references
    `local_classifier_category_in` never pays for classification at
    all (docs/DESIGN.md §9.1's "costs nothing for a config that
    doesn't use it" guarantee). If a condition *does* need it and none
    was configured, that's a startup/config error surfaced as a raised
    exception, not a silent non-match.
    """
    cached_result: list[ClassificationResult] = []

    def classify() -> ClassificationResult:
        if not cached_result:
            if classifier is None:
                raise RuntimeError(
                    "a rule condition requires a local classifier, "
                    "but none was configured (see docs/DESIGN.md §9.1)"
                )
            cached_result.append(classifier.classify(message))
        return cached_result[0]

    for rule in rules:
        if not rule.enabled:
            continue
        if _condition_matches(rule.when, message, classify):
            return RuleVerdict(action=rule.action, matched_rule_id=rule.id)

    return RuleVerdict(action=default_unmatched_action, matched_rule_id=None)
