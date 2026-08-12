"""Failure/edge-case tests for PipelineObserver (docs/DESIGN.md §12.2).

Companion to test_observer.py's acceptance tests.
"""

from __future__ import annotations

import logging

import pytest

from spork.core.pipeline.observer import PipelineObserver


class _FakeAlerter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify(self, title, body, *, url=None, urgency="normal") -> None:  # type: ignore[no-untyped-def]
        self.calls.append({"title": title, "body": body, "url": url, "urgency": urgency})


def test_alert_with_empty_title_and_body_still_delegates(caplog) -> None:
    """Degenerate but valid input — still produces a trace record and
    an Alerter call, never silently swallowed."""
    caplog.set_level(logging.INFO)
    alerter = _FakeAlerter()
    observer = PipelineObserver(alerter)

    observer.alert("corr-1", "", "")

    assert len(caplog.records) == 1
    assert alerter.calls == [{"title": "", "body": "", "url": None, "urgency": "normal"}]


def test_trace_field_colliding_with_a_reserved_logrecord_attribute_raises(caplog) -> None:
    """A field name that collides with a LogRecord's own attributes
    (e.g. "message") raises from the stdlib logging call, rather than
    silently overwriting or losing data. Documents a real constraint on
    callers of trace()/alert(): every field name passed today
    (category, band, urgency, ...) is chosen by spork's own pipeline
    modules, never by untrusted input, so this is a known caller
    contract, not a gap that needs guarding here."""
    caplog.set_level(logging.INFO)
    observer = PipelineObserver(_FakeAlerter())

    with pytest.raises(KeyError):
        observer.trace("corr-1", "event", message="this collides")
