"""MessageMeta: the concrete metadata type the message pipeline uses (§9.4).

One concrete use of the generic `spork.core.pipeline.core` framework —
`Payload`/`Filter`/`Selector`/`Pipeline` know nothing about any of the
fields defined here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from spork.core.classify.base import TextClassifier
from spork.core.models import NormalizedMessage
from spork.core.rules.engine import RuleVerdict
from spork.core.rules.schema import Action, Rule


@dataclass(frozen=True, slots=True)
class MessageMeta:
    """Everything a message-pipeline module might read or set.

    Frozen like every other value type in spork.core (`NormalizedMessage`,
    `RuleVerdict`, ...) — a module that wants to change something
    returns a new `MessageMeta` via `dataclasses.replace()`, never
    mutates the one it was given. The optional fields are unset
    (`None`) until the module responsible for them has run.
    """

    message: NormalizedMessage
    rules: Sequence[Rule]
    default_unmatched_action: Action
    classifier: TextClassifier | None = None
    verdict: RuleVerdict | None = None
    ts: str | None = None
    correlation_id: str | None = None
    audit_event: str | None = None
    audit_detail_json: str | None = None


class MissingMetaError(RuntimeError):
    """Raised when a module needs a MessageMeta field no earlier module set.

    Always a pipeline-wiring bug — a module run out of order, or used
    standalone without the module it depends on — never a normal
    per-message condition, so it's a distinct type from any error a
    module's own dependency (the rule engine, the action executor, ...)
    might raise.
    """
