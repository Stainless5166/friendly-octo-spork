"""Acceptance tests for ActionExecutor (docs/DESIGN.md §9.3).

Provider-agnostic — exercised against a plain stub ActionApplier, not
any real backend. That's the whole point: ActionExecutor's own
move/tag/ignore/escalate handling is what's under test here, not any
provider's mutation logic.
"""

from __future__ import annotations

import pytest
from spork.core.actions.executor import ActionExecutionError, ActionExecutor

from spork.core.models import NormalizedMessage
from spork.core.rules.schema import Action


class _RecordingApplier:
    """A stub ActionApplier that records every apply() call it receives."""

    def __init__(self) -> None:
        self.calls: list[tuple[NormalizedMessage, Action]] = []

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        self.calls.append((message, action))


def test_executor_applies_move_action_via_the_applier(make_message) -> None:
    """A move action reaches the applier's apply() unchanged."""
    applier = _RecordingApplier()
    executor = ActionExecutor(applier)
    message = make_message()
    action = Action(type="move", mailbox="Reading")

    executor.execute(message, action)

    assert applier.calls == [(message, action)]


def test_executor_applies_tag_action_via_the_applier(make_message) -> None:
    """A tag action reaches the applier's apply() unchanged."""
    applier = _RecordingApplier()
    executor = ActionExecutor(applier)
    message = make_message()
    action = Action(type="tag", mailbox="Urgent")

    executor.execute(message, action)

    assert applier.calls == [(message, action)]


def test_executor_ignore_action_is_a_noop_applier_never_called(make_message) -> None:
    """An ignore action is a deliberate no-op — the applier is never
    invoked for it, since there's nothing to apply."""
    applier = _RecordingApplier()
    executor = ActionExecutor(applier)

    executor.execute(make_message(), Action(type="ignore"))

    assert applier.calls == []


def test_executor_rejects_escalate_action(make_message) -> None:
    """An escalate action reaching the executor is a routing bug
    upstream — escalation is Tier 2's job, never the terminal step's."""
    applier = _RecordingApplier()
    executor = ActionExecutor(applier)

    with pytest.raises(ActionExecutionError):
        executor.execute(make_message(), Action(type="escalate"))

    assert applier.calls == []


def test_executor_rejects_move_action_without_a_mailbox(make_message) -> None:
    """A move action with no mailbox set is malformed — there's nowhere
    to move the message to — and must be rejected, not silently
    forwarded to the applier."""
    applier = _RecordingApplier()
    executor = ActionExecutor(applier)

    with pytest.raises(ActionExecutionError):
        executor.execute(make_message(), Action(type="move"))

    assert applier.calls == []
