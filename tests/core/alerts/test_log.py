"""Acceptance tests for LoggingAlerter (docs/DESIGN.md §12.1).

Uses pytest's built-in `caplog` fixture — the standard way to assert
on log output, no bespoke logger-injection seam needed.
"""

from __future__ import annotations

import logging

from spork.core.alerts.log import LoggingAlerter


def test_notify_logs_the_title_and_body(caplog) -> None:
    """A basic alert's title and body both land in the log record."""
    caplog.set_level(logging.INFO)

    LoggingAlerter().notify("Low confidence", "A message needs review.")

    assert "Low confidence" in caplog.text
    assert "A message needs review." in caplog.text


def test_notify_defaults_to_normal_urgency_at_warning_level(caplog) -> None:
    """Omitting urgency= uses "normal" — logged at WARNING."""
    caplog.set_level(logging.INFO)

    LoggingAlerter().notify("Title", "Body")

    assert caplog.records[0].levelno == logging.WARNING


def test_notify_logs_low_urgency_at_info_level(caplog) -> None:
    caplog.set_level(logging.INFO)

    LoggingAlerter().notify("Title", "Body", urgency="low")

    assert caplog.records[0].levelno == logging.INFO


def test_notify_logs_critical_urgency_at_error_level(caplog) -> None:
    caplog.set_level(logging.INFO)

    LoggingAlerter().notify("Title", "Body", urgency="critical")

    assert caplog.records[0].levelno == logging.ERROR


def test_notify_appends_the_url_to_the_body_when_given(caplog) -> None:
    """Desktop notifications (and log lines) have no first-class link
    target — a given url is appended rather than silently dropped."""
    caplog.set_level(logging.INFO)

    LoggingAlerter().notify("Title", "Body", url="https://example.com/msg/1")

    assert "https://example.com/msg/1" in caplog.text
