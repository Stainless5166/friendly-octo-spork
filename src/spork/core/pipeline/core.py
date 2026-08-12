"""Generic Filter/Selector pipeline framework (docs/DESIGN.md §9.4).

Deliberately message-agnostic: nothing here knows about
NormalizedMessage, rules, or the state DB — that's
`spork.core.pipeline.meta`/`modules`, one concrete use of this
framework. A different pipeline (e.g. M3's Tier 2 prompt-building
chain) is meant to reuse `Payload`/`Filter`/`Selector`/`Pipeline` over
its own metadata type, not invent a second abstraction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

M = TypeVar("M")


@dataclass(frozen=True, slots=True)
class Payload(Generic[M]):
    """The (text, metadata) unit every module reads and returns.

    `text` is whatever content payload is currently in flight — a
    message body for a cleaning/prompt-building chain, left alone by a
    module that only cares about `meta`. `meta` is generic over `M`
    rather than a loose dict, so a concrete pipeline gets a concrete,
    typed metadata shape (see `spork.core.pipeline.meta.MessageMeta`)
    and mypy --strict still catches a module reading a field another
    module never set.
    """

    text: str
    meta: M


class Filter(Protocol[M]):
    """A module that transforms one Payload into another.

    Always produces exactly one output — no branching, no routing.
    Compose filters in sequence (a `Pipeline`'s `filters` list) for any
    straight-line transform chain.
    """

    def apply(self, payload: Payload[M]) -> Payload[M]: ...


class Selector(Protocol[M]):
    """A module that reads one Payload and routes it to exactly one of
    its named branches, chosen per-payload.

    The sole place branching logic lives — no Filter ever needs an
    if/else about what happens next.
    """

    def select(self, payload: Payload[M]) -> tuple[str, Payload[M]]: ...


class UnknownBranchError(KeyError):
    """Raised when a Selector returns a branch name with no matching route.

    A distinct type rather than a bare KeyError so callers (and future
    `spork doctor`-style pipeline validation) can catch precisely this
    — a real Selector/Pipeline wiring bug, not an incidental dict miss
    elsewhere.
    """


class Pipeline(Generic[M]):
    """Composes modules: a straight-line chain of Filters, optionally
    ending in a Selector whose branches are themselves Pipelines.

    Recursive by construction — a `routes` value is just another
    `Pipeline`, so an arbitrarily deep branching tree is built by
    nesting `Pipeline(...)` calls, never by teaching this class about
    what any specific branch means. An empty `Pipeline()` (no filters,
    no selector) is the identity — the natural "this branch stops
    here."
    """

    def __init__(
        self,
        filters: Sequence[Filter[M]] = (),
        *,
        selector: Selector[M] | None = None,
        routes: Mapping[str, Pipeline[M]] | None = None,
    ) -> None:
        self._filters = list(filters)
        self._selector = selector
        self._routes = dict(routes) if routes is not None else {}

    def run(self, payload: Payload[M]) -> Payload[M]:
        """Run every filter in order, then follow the selector's branch, if any."""
        for stage in self._filters:
            payload = stage.apply(payload)

        if self._selector is None:
            return payload

        branch, payload = self._selector.select(payload)
        try:
            next_pipeline = self._routes[branch]
        except KeyError as exc:
            raise UnknownBranchError(
                f"selector returned branch {branch!r}, no route for it; "
                f"known routes: {sorted(self._routes)}"
            ) from exc
        return next_pipeline.run(payload)
