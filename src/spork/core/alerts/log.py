"""LoggingAlerter: the v1 Alerter backend (docs/DESIGN.md §12.1).

Logs each alert rather than showing a GUI popup — a genuinely real
delivery channel (structured, greppable output), not a stub standing
in for the desktop-notification backend the roadmap ultimately wants.
That backend (`notify-send`, wrapping `org.freedesktop.Notifications`
over the session D-Bus) is a deliberate near-term follow-up behind the
same `Alerter` Protocol, not built this round.
"""

from __future__ import annotations

import logging

from spork.core.alerts.base import AlertUrgency

# Never used at critical urgency's own numeric level by anything else
# in stdlib logging, but WARNING is the right "a human should notice
# this" default when urgency itself is missing or unrecognized — see
# _LEVEL_BY_URGENCY.get()'s fallback below.
_LEVEL_BY_URGENCY: dict[str, int] = {
    "low": logging.INFO,
    "normal": logging.WARNING,
    "critical": logging.ERROR,
}


class LoggingAlerter:
    """Logs each alert via `logging.getLogger(__name__)`.

    Never configures handlers/formatters itself — per Python logging
    best practice, library code only emits; the application (`sporkd`'s
    entry point, docs/ROADMAP.md M7's structured-logging item) owns
    how those log records actually get displayed or stored.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        message = body if url is None else f"{body} ({url})"
        # An urgency outside AlertUrgency's Literal values can only
        # reach here past mypy's back — still logged, at a safe
        # default level, rather than losing the alert to a KeyError.
        level = _LEVEL_BY_URGENCY.get(urgency, logging.WARNING)
        self._logger.log(level, "%s: %s", title, message)
