"""Acceptance tests for PipelineObserver (docs/DESIGN.md §12.2).

The "combine logging and alerting" object: `trace()` always logs with a
correlation ID attached to the record; `alert()` does that and also
delegates to an injected `Alerter`. A fake `Alerter` stands in for
`LoggingAlerter` here — these tests are about PipelineObserver's own
behavior, not `Alerter`'s (already covered under tests/core/alerts).
"""

from __future__ import annotations

import logging

from spork.core.alerts.base import AlertUrgency
from spork.core.pipeline.observer import PipelineObserver


class _FakeAlerter:
    """Records every notify() call instead of delivering it anywhere."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        self.calls.append({"title": title, "body": body, "url": url, "urgency": urgency})


def test_trace_logs_the_event_with_correlation_id_on_the_record(caplog) -> None:
    """trace() always produces a log record; the record carries
    correlation_id so one message's lines can be grepped together."""
    caplog.set_level(logging.INFO)
    observer = PipelineObserver(_FakeAlerter())

    observer.trace("corr-1", "escalated_pending_tier2")

    assert "escalated_pending_tier2" in caplog.text
    assert caplog.records[0].correlation_id == "corr-1"


def test_trace_includes_extra_fields_on_the_record(caplog) -> None:
    """Keyword fields passed to trace() land on the record too, not just
    the event string — the point of structured logging over a plain
    message (docs/ROADMAP.md M7)."""
    caplog.set_level(logging.INFO)
    observer = PipelineObserver(_FakeAlerter())

    observer.trace("corr-1", "tier2_action_applied", category="newsletter", band="autoact")

    record = caplog.records[0]
    assert record.category == "newsletter"
    assert record.band == "autoact"


def test_alert_logs_and_delegates_to_the_alerter(caplog) -> None:
    """alert() is the single call site — it both traces and notifies,
    so a module never has to remember to do both separately."""
    caplog.set_level(logging.INFO)
    alerter = _FakeAlerter()
    observer = PipelineObserver(alerter)

    observer.alert("corr-1", "Needs review", "A low-confidence verdict came back.")

    assert "Needs review" in caplog.text
    assert alerter.calls == [
        {
            "title": "Needs review",
            "body": "A low-confidence verdict came back.",
            "url": None,
            "urgency": "normal",
        }
    ]


def test_alert_passes_through_url_and_urgency(caplog) -> None:
    """Non-default url/urgency reach the Alerter unchanged."""
    caplog.set_level(logging.INFO)
    alerter = _FakeAlerter()
    observer = PipelineObserver(alerter)

    observer.alert(
        "corr-1",
        "Budget exhausted",
        "Tier 2 skipped.",
        url="https://example.com/m/1",
        urgency="critical",
    )

    assert alerter.calls[0]["url"] == "https://example.com/m/1"
    assert alerter.calls[0]["urgency"] == "critical"


def test_two_correlation_ids_stay_distinguishable_in_the_log(caplog) -> None:
    """Two trace() calls for two different messages carry two different
    correlation_id values — never share or leak between them."""
    caplog.set_level(logging.INFO)
    observer = PipelineObserver(_FakeAlerter())

    observer.trace("corr-1", "first_event")
    observer.trace("corr-2", "second_event")

    assert caplog.records[0].correlation_id == "corr-1"
    assert caplog.records[1].correlation_id == "corr-2"
