"""Acceptance tests for spork.core.logging_setup.configure_logging() (docs/DESIGN.md §6.2, M7).

configure_logging() mutates a process-wide singleton logger
(logging.getLogger("spork")) — every test here restores its handlers
and level afterward via a local, file-scoped autouse fixture (mirrors
tests/core/classify/conftest.py's snapshot/restore pattern for the
same "module-level global state" reason), so nothing here leaks into
any other test file's use of the "spork.*" logger namespace
(spork.core.alerts.log's/spork.core.pipeline.observer's caplog-based
tests, elsewhere in this suite).
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


def test_configure_logging_defaults_the_spork_logger_to_info() -> None:
    configure_logging()

    assert logging.getLogger("spork").level == logging.INFO


def test_configure_logging_sets_the_given_level() -> None:
    configure_logging("DEBUG")

    assert logging.getLogger("spork").level == logging.DEBUG


def test_configure_logging_writes_a_line_to_the_given_stream() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)

    logging.getLogger("spork.pipeline").info("hello there")

    assert "hello there" in stream.getvalue()


def test_configure_logging_output_includes_level_and_logger_name() -> None:
    """Journal-friendly: no timestamp (journald stamps its own), but
    level + logger name so spork.pipeline/spork.daemon.loop/etc. lines
    are distinguishable from each other."""
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)

    logging.getLogger("spork.daemon.loop").warning("careful")

    output = stream.getvalue()
    assert "WARNING" in output
    assert "spork.daemon.loop" in output
    assert "careful" in output


def test_configure_logging_respects_the_configured_level() -> None:
    """A DEBUG-level message is dropped when configured at INFO."""
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)

    logging.getLogger("spork.pipeline").debug("too quiet to show")

    assert stream.getvalue() == ""


def test_configure_logging_is_idempotent_not_accumulating_handlers() -> None:
    """A second call replaces the handler rather than adding a second
    one — logging once after two configure_logging() calls produces
    exactly one line, not two."""
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)
    configure_logging("INFO", stream=stream)

    logging.getLogger("spork.pipeline").info("only once")

    assert stream.getvalue().count("only once") == 1
