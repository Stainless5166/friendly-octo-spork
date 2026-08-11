"""Failure/edge-case tests for ActionExecutor.

Companion to test_executor.py's acceptance tests.
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


class _FailingApplier:
    """A stub ActionApplier that always raises, simulating a real
    backend mutation failure (e.g. a JMAP Email/set call rejected)."""

    def apply(self, message: NormalizedMessage, action: Action) -> None:
        raise RuntimeError("simulated backend failure")


def test_executor_rejects_tag_action_without_a_mailbox(make_message) -> None:
    """Same as the move case in the acceptance tests, but for tag —
    both mailbox-required action types get the same validation."""
    applier = _RecordingApplier()
    executor = ActionExecutor(applier)

    with pytest.raises(ActionExecutionError):
        executor.execute(make_message(), Action(type="tag"))

    assert applier.calls == []


def test_executor_propagates_applier_failure(make_message) -> None:
    """If the applier itself raises (a real backend mutation failing),
    that exception propagates rather than being silently swallowed —
    the daemon needs to know an action didn't actually apply."""
    executor = ActionExecutor(_FailingApplier())

    with pytest.raises(RuntimeError):
        executor.execute(make_message(), Action(type="move", mailbox="Reading"))
