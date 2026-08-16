"""Property-based tests for ActionExecutor (docs/DESIGN.md §16.1).

Companion to test_executor.py/test_executor_edge_cases.py's example-based
tests. `execute()`'s whole job is a small set of guardrails around
`type`/`mailbox` — cheap to state exhaustively as properties over
Hypothesis-generated Actions rather than one example per branch.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from spork.core.actions.executor import ActionExecutionError, ActionExecutor
from spork.core.models import NormalizedMessage
from spork.core.rules.schema import Action

_ACTION_TYPES = st.sampled_from(["move", "tag", "escalate", "ignore"])
_MAILBOXES = st.none() | st.text(max_size=20)

# execute() never reads message content (it only inspects `action`), so
# one fixed message is enough — and avoids Hypothesis's function-scoped
# fixture health check, which flags reusing a pytest fixture across
# @given's many generated examples per test call.
_MESSAGE = NormalizedMessage(
    message_id="msg-1",
    thread_id="thread-1",
    from_address="someone@example.com",
    from_domain="example.com",
    subject="Test subject",
    body_text="Test body.",
)


class _RecordingApplier:
    """A stub ActionApplier that records every apply() call it receives."""

    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, Action]] = []

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self.calls.append((message, action))


@st.composite
def _actions(draw: st.DrawFn) -> Action:
    """An arbitrary Action, spanning every type/mailbox combination —
    including the "wrong" pairings (escalate with a mailbox set, ignore
    with one too) execute() must still handle by type alone."""
    return Action(
        type=draw(_ACTION_TYPES),
        mailbox=draw(_MAILBOXES),
        reason=draw(st.none() | st.text(max_size=20)),
        alert_immediately=draw(st.booleans()),
    )


@given(action=_actions())
def test_escalate_always_rejected_and_never_reaches_the_applier(action: Action) -> None:
    """Any escalate action — whatever its mailbox/reason/alert_immediately —
    is rejected outright, for every generated variant, not just the bare
    Action(type="escalate") the acceptance test happens to construct."""
    if action.type != "escalate":
        return
    applier = _RecordingApplier()
    executor = ActionExecutor(applier)

    try:
        executor.execute(_MESSAGE, action)
        raised = False
    except ActionExecutionError:
        raised = True

    assert raised
    assert applier.calls == []


@given(action=_actions())
def test_move_or_tag_without_mailbox_always_rejected(action: Action) -> None:
    """Every move/tag Action with mailbox=None is rejected, regardless of
    what reason/alert_immediately Hypothesis generates alongside it."""
    if action.type not in ("move", "tag") or action.mailbox is not None:
        return
    applier = _RecordingApplier()
    executor = ActionExecutor(applier)

    try:
        executor.execute(_MESSAGE, action)
        raised = False
    except ActionExecutionError:
        raised = True

    assert raised
    assert applier.calls == []


@given(action=_actions())
def test_move_or_tag_with_a_mailbox_always_reaches_the_applier_unchanged(action: Action) -> None:
    """Every move/tag Action carrying a mailbox reaches apply() exactly
    once, with the exact Action object passed in — no branch here should
    ever mutate or substitute it."""
    if action.type not in ("move", "tag") or action.mailbox is None:
        return
    applier = _RecordingApplier()
    executor = ActionExecutor(applier)
    executor.execute(_MESSAGE, action)

    assert applier.calls == [(_MESSAGE, action)]


@given(action=_actions())
def test_ignore_is_always_a_pure_no_op(action: Action) -> None:
    """An ignore action never reaches the applier and never raises,
    whatever mailbox/reason/alert_immediately it happens to carry —
    those fields are meaningless for this type and must stay that way."""
    if action.type != "ignore":
        return
    applier = _RecordingApplier()
    executor = ActionExecutor(applier)

    executor.execute(_MESSAGE, action)

    assert applier.calls == []


@given(action=_actions())
def test_execute_never_both_raises_and_calls_the_applier(action: Action) -> None:
    """Across every generated Action, execute() never both rejects an
    action *and* applies it — raising and calling the applier are
    mutually exclusive outcomes for any single call (ignore's silent
    no-op is a third, deliberate outcome — see test_ignore_is_always_a_pure_no_op)."""
    applier = _RecordingApplier()
    executor = ActionExecutor(applier)

    raised = False
    try:
        executor.execute(_MESSAGE, action)
    except ActionExecutionError:
        raised = True

    assert len(applier.calls) in (0, 1)
    assert not (raised and applier.calls)
