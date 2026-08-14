"""TracingStage/TracingSelector: generic per-stage instrumentation (docs/DESIGN.md §9.4, M7).

Not built into `core.py` itself — `Pipeline`/`Filter`/`Selector`/
`Augment` stay message-agnostic (§9.4's own design), and these two
wrappers are a separate, dependency-free concern layered on top at
composition time (`build_default_pipeline()`/`build_tier2_pipeline()`,
§9.4/§10.7), not a change to the framework or to any of the concrete
modules it wraps.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Generic, TypeVar

from spork.core.pipeline.core import Augment, Filter, Payload, Selector, Stage
from spork.core.pipeline.observer import PipelineObserver

M = TypeVar("M")


def _correlation_id(meta: object) -> str:
    """`payload.meta.correlation_id` if present and set, else a
    placeholder — duck-typed rather than a new `Protocol` bound on `M`
    so this stays reusable for any future `Payload` metadata type that
    happens to expose one, not hardcoded to `MessageMeta`/`Tier2Meta`."""
    return getattr(meta, "correlation_id", None) or "-"


class TracingStage(Generic[M]):
    """Wraps any `Filter[M]`/`Augment[M]`, tracing one `ops.trace()`
    call after it runs.

    Always presents as a plain `Filter[M]` to the outer `Pipeline.run()`
    (only `.apply()`) regardless of whether the wrapped stage is really
    a `Filter` or an `Augment` — `Pipeline.run()`'s own `isinstance`
    dispatch only ever sees this wrapper, so it does the same
    `isinstance(stage, Augment)` check itself internally to call the
    wrapped stage's real method. Wrapping never changes what actually
    executes, only what gets logged around it.
    """

    def __init__(self, stage: Stage[M], ops: PipelineObserver) -> None:
        self._stage = stage
        self._ops = ops

    def apply(self, payload: Payload[M]) -> Payload[M]:
        start = time.monotonic()
        if isinstance(self._stage, Augment):
            result = self._stage.augment(payload)
            kind = "augment"
        else:
            result = self._stage.apply(payload)
            kind = "filter"
        duration_ms = round((time.monotonic() - start) * 1000, 3)
        self._ops.trace(
            _correlation_id(payload.meta),
            f"{type(self._stage).__name__} ran",
            kind=kind,
            duration_ms=duration_ms,
        )
        return result


class TracingSelector(Generic[M]):
    """Wraps any `Selector[M]`, tracing one `ops.trace()` call —
    including which branch was chosen — after it runs."""

    def __init__(self, selector: Selector[M], ops: PipelineObserver) -> None:
        self._selector = selector
        self._ops = ops

    def select(self, payload: Payload[M]) -> tuple[str, Payload[M]]:
        start = time.monotonic()
        branch, result = self._selector.select(payload)
        duration_ms = round((time.monotonic() - start) * 1000, 3)
        self._ops.trace(
            _correlation_id(payload.meta),
            f"{type(self._selector).__name__} selected",
            branch=branch,
            duration_ms=duration_ms,
        )
        return branch, result


def wrap_stages(stages: Sequence[Stage[M]], ops: PipelineObserver) -> list[Filter[M]]:
    """`TracingStage`-wrap every element of `stages`, preserving order."""
    return [TracingStage(stage, ops) for stage in stages]


def wrap_selector(selector: Selector[M], ops: PipelineObserver) -> Selector[M]:
    """`TracingSelector`-wrap `selector`."""
    return TracingSelector(selector, ops)
