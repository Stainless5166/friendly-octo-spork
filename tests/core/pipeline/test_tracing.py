"""Acceptance tests for spork.core.pipeline.tracing (docs/DESIGN.md §9.4, M7).

Generic over a minimal local metadata type (_Meta, correlation_id
only) rather than MessageMeta/Tier2Meta — proves TracingStage/
TracingSelector are actually reusable for any Payload metadata type
that happens to expose one, not hardcoded to either concrete pipeline.
Trace output asserted via caplog, same as PipelineObserver's own
tests — no configure_logging() involved, PipelineObserver.trace()
always logs regardless.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

from spork.core.pipeline.core import Payload
from spork.core.pipeline.observer import PipelineObserver
from spork.core.pipeline.tracing import TracingSelector, TracingStage, wrap_selector, wrap_stages


@dataclass(frozen=True, slots=True)
class _Meta:
    correlation_id: str | None = None


class _FakeAlerter:
    def notify(self, title, body, *, url=None, urgency="normal") -> None:  # type: ignore[no-untyped-def]
        pass


class _StubFilter:
    def __init__(self) -> None:
        self.calls = 0

    def apply(self, payload: Payload[_Meta]) -> Payload[_Meta]:
        self.calls += 1
        return Payload(text=payload.text + "-filtered", meta=payload.meta)


class _StubAugment:
    def __init__(self) -> None:
        self.calls = 0

    def augment(self, payload: Payload[_Meta]) -> Payload[_Meta]:
        self.calls += 1
        return Payload(text=payload.text + "-augmented", meta=payload.meta)


class _StubSelector:
    def __init__(self, branch: str) -> None:
        self.calls = 0
        self._branch = branch

    def select(self, payload: Payload[_Meta]) -> tuple[str, Payload[_Meta]]:
        self.calls += 1
        return self._branch, payload


def _ops() -> PipelineObserver:
    return PipelineObserver(_FakeAlerter())


def test_tracing_stage_delegates_to_the_wrapped_filter(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    stub = _StubFilter()
    payload = Payload(text="hi", meta=_Meta(correlation_id="cid-1"))

    result = TracingStage(stub, _ops()).apply(payload)

    assert stub.calls == 1
    assert result.text == "hi-filtered"


def test_tracing_stage_delegates_to_the_wrapped_augment_via_augment_not_apply(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The real point: a TracingStage wrapping an Augment still calls
    .augment() on it, not .apply() — Pipeline.run()'s own isinstance
    dispatch only ever sees the wrapper's .apply(), so the wrapper has
    to do the right internal dispatch itself."""
    caplog.set_level(logging.INFO)
    stub = _StubAugment()
    payload = Payload(text="hi", meta=_Meta(correlation_id="cid-1"))

    result = TracingStage(stub, _ops()).apply(payload)

    assert stub.calls == 1
    assert result.text == "hi-augmented"


def test_tracing_stage_traces_the_wrapped_stage_name(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    payload = Payload(text="hi", meta=_Meta(correlation_id="cid-1"))

    TracingStage(_StubFilter(), _ops()).apply(payload)

    assert "_StubFilter" in caplog.text


def test_tracing_stage_includes_the_correlation_id_in_the_trace(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    payload = Payload(text="hi", meta=_Meta(correlation_id="cid-42"))

    TracingStage(_StubFilter(), _ops()).apply(payload)

    assert caplog.records[0].correlation_id == "cid-42"


def test_tracing_stage_defaults_correlation_id_when_meta_has_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Runs before CorrelationIdFilter (the first stage or two) never
    crash for lack of one — a placeholder, not an exception."""
    caplog.set_level(logging.INFO)
    payload = Payload(text="hi", meta=_Meta(correlation_id=None))

    TracingStage(_StubFilter(), _ops()).apply(payload)

    assert caplog.records[0].correlation_id == "-"


def test_tracing_stage_includes_duration_ms(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    payload = Payload(text="hi", meta=_Meta(correlation_id="cid-1"))

    TracingStage(_StubFilter(), _ops()).apply(payload)

    assert hasattr(caplog.records[0], "duration_ms")


def test_tracing_selector_delegates_to_the_wrapped_selector(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    stub = _StubSelector("terminal")
    payload = Payload(text="hi", meta=_Meta(correlation_id="cid-1"))

    branch, result = TracingSelector(stub, _ops()).select(payload)

    assert stub.calls == 1
    assert branch == "terminal"
    assert result is payload


def test_tracing_selector_traces_the_chosen_branch(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    payload = Payload(text="hi", meta=_Meta(correlation_id="cid-1"))

    TracingSelector(_StubSelector("escalate"), _ops()).select(payload)

    assert "_StubSelector" in caplog.text
    assert caplog.records[0].branch == "escalate"


def test_wrap_stages_wraps_every_element_preserving_order() -> None:
    a, b = _StubFilter(), _StubAugment()

    wrapped = wrap_stages([a, b], _ops())

    assert len(wrapped) == 2
    assert all(isinstance(stage, TracingStage) for stage in wrapped)


def test_wrap_stages_wrapped_list_still_runs_in_order(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    a, b = _StubFilter(), _StubAugment()
    payload = Payload(text="start", meta=_Meta(correlation_id="cid-1"))

    for stage in wrap_stages([a, b], _ops()):
        payload = stage.apply(payload)

    assert payload.text == "start-filtered-augmented"


def test_wrap_selector_wraps_the_given_selector() -> None:
    stub = _StubSelector("terminal")

    wrapped = wrap_selector(stub, _ops())

    assert isinstance(wrapped, TracingSelector)
