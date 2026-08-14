"""Failure/edge-case tests for spork.core.logging_setup.configure_logging().

Companion to test_logging_setup.py's acceptance tests — covers the two
_JournalFriendlyFormatter branches the acceptance round didn't reach:
extra fields (the mechanism PipelineObserver.trace() already relies on
for correlation_id) and exception info.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator

import pytest

from spork.core.logging_setup import configure_logging


@pytest.fixture(autouse=True)
def _isolate_spork_logger() -> Iterator[None]:
    logger = logging.getLogger("spork")
    original_handlers = list(logger.handlers)
    original_level = logger.level
    try:
        yield
    finally:
        logger.handlers.clear()
        logger.handlers.extend(original_handlers)
        logger.setLevel(original_level)


def test_configure_logging_appends_extra_fields_as_key_value_pairs() -> None:
    """The exact mechanism PipelineObserver.trace() uses for
    correlation_id — a record with extra={...} shows those fields in
    the formatted line, not just the base message."""
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)

    logging.getLogger("spork.pipeline").info(
        "TimestampFilter ran", extra={"correlation_id": "abc123", "duration_ms": 5}
    )

    output = stream.getvalue()
    assert "correlation_id=abc123" in output
    assert "duration_ms=5" in output


def test_configure_logging_includes_exception_info_when_logged_with_exc_info() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)

    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("spork.pipeline").exception("something failed")

    output = stream.getvalue()
    assert "something failed" in output
    assert "ValueError: boom" in output


def test_configure_logging_raises_valueerror_for_an_unknown_level() -> None:
    with pytest.raises(ValueError, match="Unknown level"):
        configure_logging("VERBOSE")
