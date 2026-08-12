"""Failure/edge-case tests for LoggingAlerter.

Companion to test_log.py's acceptance tests.
"""

from __future__ import annotations

import logging

from spork.core.alerts.log import LoggingAlerter


def test_notify_falls_back_to_warning_for_an_unrecognized_urgency(caplog) -> None:
    """A caller ignoring AlertUrgency's Literal contract (reachable
    only past mypy, e.g. a value read from untrusted config) still
    gets the alert logged, at a safe default level — not a raw
    KeyError that would lose the alert entirely."""
    caplog.set_level(logging.INFO)

    LoggingAlerter().notify("Title", "Body", urgency="urgent")  # type: ignore[arg-type]

    assert caplog.records[0].levelno == logging.WARNING
    assert "Title" in caplog.text


def test_notify_with_an_empty_title_and_body_still_logs(caplog) -> None:
    """Degenerate but valid input — an alert with nothing to say still
    produces a log record, not a silent no-op."""
    caplog.set_level(logging.INFO)

    LoggingAlerter().notify("", "")

    assert len(caplog.records) == 1


def test_each_notify_call_produces_its_own_log_record(caplog) -> None:
    """Two separate alerts produce two separate records, in order —
    not deduplicated or batched."""
    caplog.set_level(logging.INFO)

    LoggingAlerter().notify("First", "one")
    LoggingAlerter().notify("Second", "two")

    assert len(caplog.records) == 2
    assert "First" in caplog.records[0].getMessage()
    assert "Second" in caplog.records[1].getMessage()


def test_the_logger_name_follows_the_module_for_future_per_package_filtering(caplog) -> None:
    """logging.getLogger(__name__) means the logger is named
    "spork.core.alerts.log" — so a future per-package log-level
    config (docs/ROADMAP.md M7) can target alerts specifically."""
    caplog.set_level(logging.INFO)

    LoggingAlerter().notify("Title", "Body")

    assert caplog.records[0].name == "spork.core.alerts.log"
