"""Property-based tests for process_message() (docs/DESIGN.md §16.1).

Companion to test_default.py/test_default_edge_cases.py's example-based
tests. These state invariants about the *tying-together* job
process_message() does — idempotency, escalate vs. terminal handling,
force bypass, and faithfulness to the rule engine's own decision — over
Hypothesis-generated messages and rule sets, not one scenario each.

Uses `tmp_path_factory` (session-scoped) rather than `tmp_path`
(function-scoped) so a fresh StateDB file is created per Hypothesis
example inside the test body — `tmp_path` itself would trip Hypothesis's
function-scoped-fixture health check (it isn't reset between examples).
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from spork.core.actions.executor import ActionExecutor
from spork.core.alerts.base import AlertUrgency
from spork.core.models import NormalizedMessage
from spork.core.pipeline import process_message
from spork.core.pipeline.observer import PipelineObserver
from spork.core.rules.engine import evaluate as engine_evaluate
from spork.core.rules.schema import Action, Condition, Rule
from spork.core.state.db import StateDB


class _RecordingApplier:
    """A stub ActionApplier that records every apply() call it receives."""

    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, Action]] = []

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self.calls.append((message, action))


class _FakeAlerter:
    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        pass


@st.composite
def _messages(draw: st.DrawFn) -> NormalizedMessage:
    """An arbitrary NormalizedMessage — message_id varies too, since
    idempotency keys off it."""
    return NormalizedMessage(
        message_id=draw(st.text(min_size=1, max_size=12)),
        thread_id=draw(st.text(min_size=1, max_size=12)),
        from_address=draw(st.text(max_size=20)),
        from_domain=draw(st.text(max_size=20)),
        subject=draw(st.text(max_size=20)),
        body_text=draw(st.text(max_size=20)),
    )


@st.composite
def _safe_actions(draw: st.DrawFn) -> Action:
    """Any Action shape ActionExecutor accepts without raising — move/tag
    always carry a mailbox, so a run never fails for a reason unrelated
    to what these properties are checking."""
    action_type = draw(st.sampled_from(["move", "tag", "ignore", "escalate"]))
    mailbox = draw(st.text(min_size=1, max_size=8)) if action_type in ("move", "tag") else None
    return Action(type=action_type, mailbox=mailbox)


@st.composite
def _rule_lists(draw: st.DrawFn) -> list[Rule]:
    """A small list of rules mixing always-matching and never-matching
    conditions, enabled and disabled, terminal and escalate actions —
    enough variety to exercise RuleEvaluationSelector's routing."""
    count = draw(st.integers(min_value=0, max_value=5))
    return [
        Rule(
            id=f"r{i}",
            when=draw(st.sampled_from([Condition(always=True), Condition()])),
            action=draw(_safe_actions()),
            enabled=draw(st.booleans()),
        )
        for i in range(count)
    ]


@given(
    message=_messages(),
    action_type=st.sampled_from(["move", "tag", "ignore"]),
)
def test_process_message_never_applies_a_terminal_action_twice(
    tmp_path_factory, message: NormalizedMessage, action_type: str
) -> None:
    """Running the same message through process_message() twice never
    applies its action a second time — the idempotency guarantee, for
    any generated message and terminal action type."""
    mailbox = "X" if action_type in ("move", "tag") else None
    rules = [
        Rule(id="r1", when=Condition(always=True), action=Action(type=action_type, mailbox=mailbox))
    ]
    applier = _RecordingApplier()
    db_path = tmp_path_factory.mktemp("state") / "state.sqlite3"

    with StateDB(db_path) as db:
        first = process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t1",
        )
        second = process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
            now=lambda: "t2",
        )

    assert first is not None
    assert second is None
    # ignore is a deliberate no-op (ActionExecutor never calls the
    # applier for it) — every other terminal type applies exactly once.
    assert len(applier.calls) == (0 if action_type == "ignore" else 1)


@given(message=_messages())
def test_escalate_verdict_never_marks_processed_or_applies(
    tmp_path_factory, message: NormalizedMessage
) -> None:
    """Whatever the generated message, an escalate verdict is recorded
    as pending — never marked processed, never sent to the applier —
    since Tier 2 owns the terminal mark (docs/DESIGN.md §9)."""
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="escalate"))]
    applier = _RecordingApplier()
    db_path = tmp_path_factory.mktemp("state") / "state.sqlite3"

    with StateDB(db_path) as db:
        verdict = process_message(
            message,
            rules,
            default_unmatched_action=Action(type="ignore"),
            executor=ActionExecutor(applier),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
        )
        marked = db.has_processed(message.message_id)

    assert verdict is not None
    assert verdict.action.type == "escalate"
    assert marked is False
    assert applier.calls == []


@given(message=_messages(), action_type=st.sampled_from(["move", "tag", "ignore"]))
def test_non_escalate_verdict_always_marks_processed(
    tmp_path_factory, message: NormalizedMessage, action_type: str
) -> None:
    """Every terminal (non-escalate) verdict marks the message processed
    — the complement of the escalate property above, for any generated
    message and terminal action type."""
    mailbox = "X" if action_type in ("move", "tag") else None
    rules = [
        Rule(id="r1", when=Condition(always=True), action=Action(type=action_type, mailbox=mailbox))
    ]
    db_path = tmp_path_factory.mktemp("state") / "state.sqlite3"

    with StateDB(db_path) as db:
        verdict = process_message(
            message,
            rules,
            default_unmatched_action=Action(type="escalate"),
            executor=ActionExecutor(_RecordingApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
        )
        marked = db.has_processed(message.message_id)

    assert verdict is not None
    assert marked is True


@given(message=_messages())
def test_force_bypasses_idempotency_on_every_call(
    tmp_path_factory, message: NormalizedMessage
) -> None:
    """force=True re-evaluates and re-applies on every call, even the
    second time around on the same message — the idempotency gate is
    skipped entirely, not consulted-and-overridden (default.py's
    build_default_pipeline() docstring)."""
    rules = [Rule(id="r1", when=Condition(always=True), action=Action(type="tag", mailbox="X"))]
    applier = _RecordingApplier()
    db_path = tmp_path_factory.mktemp("state") / "state.sqlite3"

    with StateDB(db_path) as db:
        for _ in range(2):
            verdict = process_message(
                message,
                rules,
                default_unmatched_action=Action(type="escalate"),
                executor=ActionExecutor(applier),
                state_db=db,
                ops=PipelineObserver(_FakeAlerter()),
                force=True,
            )
            assert verdict is not None

    assert len(applier.calls) == 2


@given(message=_messages(), rules=_rule_lists())
def test_process_message_verdict_matches_the_rule_engines_own_evaluate(
    tmp_path_factory, message: NormalizedMessage, rules: list[Rule]
) -> None:
    """process_message()'s RuleEvaluationSelector routing must never
    diverge from calling spork.core.rules.engine.evaluate() directly
    with the same inputs — an independent oracle for the pipeline's
    wiring, not just the engine's own logic (already covered by
    test_engine_fuzz.py)."""
    default_action = Action(type="ignore")
    reference = engine_evaluate(message, rules, default_unmatched_action=default_action)
    db_path = tmp_path_factory.mktemp("state") / "state.sqlite3"

    with StateDB(db_path) as db:
        verdict = process_message(
            message,
            rules,
            default_unmatched_action=default_action,
            executor=ActionExecutor(_RecordingApplier()),
            state_db=db,
            ops=PipelineObserver(_FakeAlerter()),
        )

    assert verdict == reference
