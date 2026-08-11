"""ActionExecutor: applies a rule engine verdict's terminal action (§9.3).

Provider-agnostic — takes whatever `ActionApplier` a `Provider`'s
`build_action_applier()` returns and applies `move`/`tag`/`ignore`
actions through it. Rejects `escalate` outright: reaching this class
with one means something upstream routed a Tier-2-only action to the
terminal step by mistake (docs/DESIGN.md §9).
"""

from __future__ import annotations

from spork.core.models import NormalizedMessage
from spork.core.providers.base import ActionApplier
from spork.core.rules.schema import Action

# move/tag both name a destination mailbox; ignore and escalate don't.
_MAILBOX_REQUIRED_ACTIONS = frozenset({"move", "tag"})


class ActionExecutionError(ValueError):
    """Raised when an Action can't be executed as given.

    Covers both ways a verdict can reach this class malformed: an
    `escalate` action (a routing bug — escalation belongs to Tier 2,
    never the terminal step), or a `move`/`tag` action with no
    `mailbox` set (nowhere to actually move/tag the message to).
    """


class ActionExecutor:
    """Applies a Rule/verdict `Action` via an injected `ActionApplier`."""

    def __init__(self, applier: ActionApplier) -> None:
        self._applier = applier

    def execute(self, message: NormalizedMessage, action: Action) -> None:
        """Apply `action` to `message` — or reject it outright.

        `ignore` is a deliberate no-op: the applier is never invoked,
        since there's nothing to apply.
        """
        if action.type == "escalate":
            raise ActionExecutionError(
                f"ActionExecutor cannot execute an escalate action: {action!r} — "
                "escalation is Tier 2's job, not the terminal action step"
            )
        if action.type in _MAILBOX_REQUIRED_ACTIONS and action.mailbox is None:
            raise ActionExecutionError(
                f"{action.type} action requires a mailbox, got None: {action!r}"
            )
        if action.type == "ignore":
            return
        self._applier.apply(message, action)
