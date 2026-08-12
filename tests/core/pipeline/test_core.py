"""Acceptance tests for the generic pipeline framework (docs/DESIGN.md §9.4).

Uses a plain `int` as the metadata type to prove Payload/Filter/
Selector/Pipeline are genuinely generic — no message/rule/state-DB
knowledge anywhere in this module. The message-specific pipeline
(MessageMeta + the concrete Filters/Selectors that reproduce M2's
process_message()) is tested separately in test_meta.py/test_modules.py.
"""

from __future__ import annotations

import dataclasses

import pytest

from spork.core.pipeline.core import Payload, Pipeline, UnknownBranchError


class _AppendFilter:
    """Appends a fixed suffix to payload.text; leaves meta untouched."""

    def __init__(self, suffix: str) -> None:
        self._suffix = suffix

    def apply(self, payload: Payload[int]) -> Payload[int]:
        return dataclasses.replace(payload, text=payload.text + self._suffix)


class _IncrementMetaFilter:
    """Increments the int meta by one — proves a Filter can update meta,
    not just text."""

    def apply(self, payload: Payload[int]) -> Payload[int]:
        return dataclasses.replace(payload, meta=payload.meta + 1)


class _FixedBranchSelector:
    """Always routes to a fixed, pre-configured branch name."""

    def __init__(self, branch: str) -> None:
        self._branch = branch

    def select(self, payload: Payload[int]) -> tuple[str, Payload[int]]:
        return self._branch, payload


class _AddContextAugment:
    """Appends a fixed piece of "looked-up" context to payload.text —
    stands in for a real Augment (e.g. a thread-history or contact
    lookup) without a real dependency: proves Pipeline dispatches to
    `.augment()`, not what the lookup itself does."""

    def __init__(self, context: str) -> None:
        self._context = context

    def augment(self, payload: Payload[int]) -> Payload[int]:
        return dataclasses.replace(payload, text=payload.text + self._context)


class _IncrementMetaAugment:
    """Increments int meta — proves an Augment can enrich meta, not
    just text, same as a Filter can."""

    def augment(self, payload: Payload[int]) -> Payload[int]:
        return dataclasses.replace(payload, meta=payload.meta + 1)


def test_pipeline_runs_filters_in_order() -> None:
    """A straight-line chain of Filters applies each in sequence."""
    pipeline = Pipeline([_AppendFilter("a"), _AppendFilter("b"), _AppendFilter("c")])

    result = pipeline.run(Payload(text="", meta=0))

    assert result.text == "abc"


def test_empty_pipeline_is_the_identity() -> None:
    """No filters, no selector: the payload passes through unchanged —
    the natural "this branch stops here" building block."""
    pipeline: Pipeline[int] = Pipeline()

    result = pipeline.run(Payload(text="unchanged", meta=42))

    assert result == Payload(text="unchanged", meta=42)


def test_pipeline_with_a_selector_routes_to_the_chosen_branch() -> None:
    """A Pipeline ending in a Selector runs only the route the selector
    chose — the other route's filters never execute."""
    pipeline = Pipeline(
        selector=_FixedBranchSelector("a"),
        routes={
            "a": Pipeline([_AppendFilter("-a-branch")]),
            "b": Pipeline([_AppendFilter("-b-branch")]),
        },
    )

    result = pipeline.run(Payload(text="start", meta=0))

    assert result.text == "start-a-branch"


def test_pipeline_branches_compose_recursively() -> None:
    """A route's Pipeline can itself end in a Selector — branching
    composes by nesting Pipeline(...) calls, with no special-casing in
    Pipeline itself for "this route branches again"."""
    inner = Pipeline(
        selector=_FixedBranchSelector("deep"),
        routes={"deep": Pipeline([_AppendFilter("-deep")])},
    )
    outer = Pipeline(
        selector=_FixedBranchSelector("outer"),
        routes={"outer": inner},
    )

    result = outer.run(Payload(text="start", meta=0))

    assert result.text == "start-deep"


def test_unknown_branch_name_raises_a_clear_error() -> None:
    """A Selector returning a branch name with no matching route is a
    clear UnknownBranchError, not a raw KeyError."""
    pipeline = Pipeline(selector=_FixedBranchSelector("nonexistent"), routes={"known": Pipeline()})

    with pytest.raises(UnknownBranchError):
        pipeline.run(Payload(text="", meta=0))


def test_filters_can_update_meta_not_just_text() -> None:
    """Filters aren't limited to transforming text — meta is just as
    mutable (via a new Payload), which is how a real pipeline threads
    state like a verdict or a timestamp through."""
    pipeline = Pipeline([_IncrementMetaFilter(), _IncrementMetaFilter(), _IncrementMetaFilter()])

    result = pipeline.run(Payload(text="", meta=0))

    assert result.meta == 3


def test_pipeline_runs_augments_via_their_augment_method() -> None:
    """A stage that only implements `.augment()` (no `.apply()`) runs
    correctly in a Pipeline's stage list — Augment is a first-class
    stage type, not a Filter in disguise."""
    pipeline = Pipeline([_AddContextAugment("[context]")])

    result = pipeline.run(Payload(text="start", meta=0))

    assert result.text == "start[context]"


def test_pipeline_interleaves_filters_and_augments_in_call_order() -> None:
    """Filters and Augments compose freely in one ordered stage list —
    the split is about intent (I/O or not), not about where a stage is
    allowed to sit."""
    pipeline = Pipeline(
        [
            _AppendFilter("-clean"),
            _AddContextAugment("-context"),
            _AppendFilter("-final"),
        ]
    )

    result = pipeline.run(Payload(text="start", meta=0))

    assert result.text == "start-clean-context-final"


def test_augment_can_update_meta_not_just_text() -> None:
    """Same meta-mutation contract as Filter — an Augment enriching
    meta (e.g. attaching a looked-up contact record) is how a real
    lookup makes its result visible downstream."""
    pipeline = Pipeline([_IncrementMetaAugment(), _IncrementMetaAugment()])

    result = pipeline.run(Payload(text="", meta=0))

    assert result.meta == 2


def test_augment_then_selector_pipeline_composes_like_a_filter_would() -> None:
    """An Augment-then-Selector Pipeline works the same way a
    Filter-then-Selector one does — Augment doesn't need special-case
    support anywhere but the stage-dispatch loop."""
    pipeline = Pipeline(
        [_AddContextAugment("-context")],
        selector=_FixedBranchSelector("a"),
        routes={"a": Pipeline([_AppendFilter("-a-branch")])},
    )

    result = pipeline.run(Payload(text="start", meta=0))

    assert result.text == "start-context-a-branch"
