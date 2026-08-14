"""configure_logging(): structured application logging for sporkd/spork (docs/DESIGN.md §6.2, M7).

Distinct from `audit_log` (§7.4), which is a permanent, structured
per-decision/per-change record — this is an operational log stream
(what the daemon is *doing*, at whatever verbosity is asked for).
Configures the `"spork"` logger namespace; every module's own
`logging.getLogger("spork.xxx")` call (`PipelineObserver`'s existing
`"spork.pipeline"` included) is a child of it and inherits this setup
by normal `logging` propagation — no per-module wiring needed.
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO

_LOGGER_NAME = "spork"

# Every attribute a bare LogRecord already has, plus the two
# format-time-only pseudo-attributes (`message`/`asctime`) — anything
# else on a record came from a caller's `extra={...}` (the mechanism
# `PipelineObserver.trace()` already uses for `correlation_id` and any
# other per-event fields).
_STANDARD_RECORD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "message",
    "asctime",
}


class _JournalFriendlyFormatter(logging.Formatter):
    """`LEVEL logger.name: message key=val ...` — no timestamp, since
    journald stamps every captured line with its own real-time clock
    (docs/DESIGN.md §14) and a second one here would just be noise.
    Any `extra` fields on the record (arbitrary per call site) are
    appended generically rather than referenced by a fixed format
    string, which would `KeyError` on any record missing one.
    """

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname} {record.name}: {record.getMessage()}"
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_RECORD_ATTRS
        }
        if extras:
            base += " " + " ".join(f"{key}={value}" for key, value in sorted(extras.items()))
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging(level: str = "INFO", *, stream: TextIO | None = None) -> None:
    """Configure the `"spork"` logger namespace with one `StreamHandler`.

    `stream` defaults to `sys.stderr` — systemd captures a unit's
    stderr into the journal line-by-line automatically (§14), so no
    `systemd.journal.JournalHandler`/extra dependency is needed, same
    "no new dependency for something this small" call
    `spork.core.systemd.notify`'s hand-rolled `sd_notify` made.
    Idempotent: replaces any handler a previous call already added
    rather than accumulating a second one, so calling this more than
    once (a CLI flag overriding `config.toml`'s own value, e.g.) stays
    safe. Raises `ValueError` (via `logging.Logger.setLevel()`) for a
    `level` that isn't one of the standard level names.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    logger.handlers.clear()
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(_JournalFriendlyFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
