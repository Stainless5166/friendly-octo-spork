"""Failure/edge-case tests for the generic pipeline framework.

Companion to test_core.py's acceptance tests.
"""

from __future__ import annotations

import dataclasses

import pytest

from spork.core.pipeline.core import Payload, Pipeline, UnknownBranchError


class _AppendFilter:
    def __init__(self, suffix: str) -> None:
        self._suffix = suffix

    def apply(self, payload: Payload[int]) -> Payload[int]:
        return dataclasses.replace(payload, text=payload.text + self._suffix)


class _FixedRouteSelector:
    """Always routes to "only", without touching the payload."""

    def select(self, payload: Payload[int]) -> tuple[str, Payload[int]]:
        return "only", payload


class _TaggingSelector:
    """Appends a tag to the payload's text *and* routes — proves the
    branch pipeline sees the selector's own edits, not the pre-select
    payload."""

    def select(self, payload: Payload[int]) -> tuple[str, Payload[int]]:
        tagged = dataclasses.replace(payload, text=payload.text + "[tagged]")
        return "only", tagged


def test_payload_is_frozen() -> None:
    """Payload can't be mutated in place — same immutability contract
    as every other value type in spork.core."""
    payload = Payload(text="a", meta=1)

    with pytest.raises(dataclasses.FrozenInstanceError):
        payload.text = "b"  # type: ignore[misc]


def test_pipeline_with_only_a_selector_and_no_filters_routes_immediately() -> None:
    """A Pipeline can be selector-only (empty filters list) — the
    default empty tuple isn't required to be non-empty."""
    pipeline = Pipeline(
        selector=_FixedRouteSelector(), routes={"only": Pipeline([_AppendFilter("-done")])}
    )

    result = pipeline.run(Payload(text="start", meta=0))

    assert result.text == "start-done"


def test_branch_pipeline_receives_the_selectors_own_payload_edits() -> None:
    """The branch pipeline runs against whatever payload the selector
    returned, not the payload it was given — a selector that both
    inspects and edits the payload before routing works as expected."""
    pipeline = Pipeline(
        selector=_TaggingSelector(), routes={"only": Pipeline([_AppendFilter("-after")])}
    )

    result = pipeline.run(Payload(text="start", meta=0))

    assert result.text == "start[tagged]-after"


def test_pipeline_is_reusable_across_independent_runs() -> None:
    """The same Pipeline instance run twice with different inputs
    produces two independent, correct results — no leaked state
    between runs."""
    pipeline = Pipeline([_AppendFilter("-x")])

    first = pipeline.run(Payload(text="one", meta=0))
    second = pipeline.run(Payload(text="two", meta=0))

    assert first.text == "one-x"
    assert second.text == "two-x"


def test_unknown_branch_error_names_the_known_routes() -> None:
    """The error message names what routes *were* available, not just
    that the lookup failed — useful for debugging a pipeline wiring
    mistake."""

    class _Selector:
        def select(self, payload: Payload[int]) -> tuple[str, Payload[int]]:
            return "missing", payload

    pipeline = Pipeline(selector=_Selector(), routes={"a": Pipeline(), "b": Pipeline()})

    with pytest.raises(UnknownBranchError) as exc_info:
        pipeline.run(Payload(text="", meta=0))

    message = str(exc_info.value)
    assert "'a'" in message
    assert "'b'" in message
