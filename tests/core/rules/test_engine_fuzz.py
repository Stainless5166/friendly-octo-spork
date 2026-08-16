"""Property-based tests for the Tier 1 rule engine (docs/DESIGN.md §16.1).

Companion to test_engine.py/test_engine_edge_cases.py's example-based
tests. Those pin down specific scenarios; these state invariants that
must hold for *any* input Hypothesis generates — closing the gap 100%
line coverage alone can't: a mutated `not in`/`in` or `and`/`or` can
still execute every line and pass every hand-picked example.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from spork.core.models import NormalizedMessage
from spork.core.rules.engine import evaluate
from spork.core.rules.schema import Action, Condition, Rule

# Printable-ish text, wide enough to exercise real string
# comparison/membership without pathological control characters that
# would say nothing new about the engine's own logic (it does
# equality/membership, not parsing).
_TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc")), max_size=20)


@st.composite
def _messages(draw: st.DrawFn) -> NormalizedMessage:
    """An arbitrary NormalizedMessage — every field the engine reads varies."""
    return NormalizedMessage(
        message_id=draw(st.text(min_size=1, max_size=12)),
        thread_id=draw(st.text(min_size=1, max_size=12)),
        from_address=draw(_TEXT),
        from_domain=draw(_TEXT),
        subject=draw(_TEXT),
        body_text=draw(_TEXT),
    )


@given(enabled_flags=st.lists(st.booleans(), min_size=1, max_size=8), message=_messages())
def test_first_enabled_always_true_rule_wins_regardless_of_count(
    enabled_flags: list[bool], message: NormalizedMessage
) -> None:
    """With every rule set to unconditionally match, the winner is always
    the earliest *enabled* one — never an earlier disabled one, never a
    later one, no matter how many rules or which are enabled."""
    rules = [
        Rule(
            id=f"rule-{i}",
            when=Condition(always=True),
            action=Action(type="tag", mailbox=f"M{i}"),
            enabled=enabled,
        )
        for i, enabled in enumerate(enabled_flags)
    ]

    verdict = evaluate(message, rules, default_unmatched_action=Action(type="escalate"))

    expected_index = next((i for i, e in enumerate(enabled_flags) if e), None)
    if expected_index is None:
        assert verdict.matched_rule_id is None
        assert verdict.action == Action(type="escalate")
    else:
        assert verdict.matched_rule_id == f"rule-{expected_index}"
        assert verdict.action == Action(type="tag", mailbox=f"M{expected_index}")


@given(message=_messages(), count=st.integers(min_value=0, max_value=8))
def test_empty_conditions_never_match_any_generated_message(
    message: NormalizedMessage, count: int
) -> None:
    """An all-default Condition (no field set) never matches, for any
    number of such rules and any generated message — the "explicit but
    vacuous config isn't a silent catch-all" guarantee, generalized."""
    rules = [
        Rule(id=f"empty-{i}", when=Condition(), action=Action(type="tag", mailbox="X"))
        for i in range(count)
    ]

    verdict = evaluate(message, rules, default_unmatched_action=Action(type="ignore"))

    assert verdict.matched_rule_id is None
    assert verdict.action == Action(type="ignore")


@given(message=_messages(), domains=st.lists(_TEXT, max_size=6, unique=True))
def test_from_domain_in_matches_iff_domain_is_a_member(
    message: NormalizedMessage, domains: list[str]
) -> None:
    """A from_domain_in condition matches exactly when the message's
    from_domain is a member of the list — true for any generated domain
    list, not just a couple of hand-picked ones."""
    rule = Rule(
        id="domain-rule",
        when=Condition(from_domain_in=domains),
        action=Action(type="tag", mailbox="X"),
    )

    verdict = evaluate(message, [rule], default_unmatched_action=Action(type="ignore"))

    if message.from_domain in domains:
        assert verdict.matched_rule_id == "domain-rule"
    else:
        assert verdict.matched_rule_id is None


@given(message=_messages(), addresses=st.lists(_TEXT, max_size=6, unique=True))
def test_from_in_matches_iff_address_is_a_member(
    message: NormalizedMessage, addresses: list[str]
) -> None:
    """Same membership property as from_domain_in, for the exact-address
    condition kind — the two fields are evaluated by separate branches
    (schema.py), so each earns its own property test."""
    rule = Rule(
        id="address-rule",
        when=Condition(from_in=addresses),
        action=Action(type="tag", mailbox="X"),
    )

    verdict = evaluate(message, [rule], default_unmatched_action=Action(type="ignore"))

    if message.from_address in addresses:
        assert verdict.matched_rule_id == "address-rule"
    else:
        assert verdict.matched_rule_id is None


@given(message=_messages(), count=st.integers(min_value=1, max_value=8))
def test_disabled_rules_are_always_skipped_regardless_of_condition(
    message: NormalizedMessage, count: int
) -> None:
    """Every rule disabled, even ones that unconditionally match, always
    falls through to the default policy — enabled=False must dominate a
    matching condition for any number of such rules."""
    rules = [
        Rule(
            id=f"disabled-{i}",
            when=Condition(always=True),
            action=Action(type="tag", mailbox=f"M{i}"),
            enabled=False,
        )
        for i in range(count)
    ]

    verdict = evaluate(message, rules, default_unmatched_action=Action(type="escalate"))

    assert verdict.matched_rule_id is None
    assert verdict.action == Action(type="escalate")
