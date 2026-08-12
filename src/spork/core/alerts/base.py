"""The common contract every alert backend adapts to (docs/DESIGN.md §12.1).

Mirrors spork.core.providers.base's Provider pattern: a logging-only
backend is all that exists today, but nothing downstream of Alerter
should need to know that — a real desktop-notification backend later
is an addition, not a rewrite.
"""

from __future__ import annotations

from typing import Literal, Protocol

# Matches the Desktop Notifications Specification's own urgency
# vocabulary (https://specifications.freedesktop.org/notification/1.2/urgency-levels.html)
# and notify-send(1)'s -u/--urgency flag values exactly — confirmed
# against both before settling this, not guessed. Low/normal don't
# need to interrupt; critical notifications shouldn't auto-expire.
AlertUrgency = Literal["low", "normal", "critical"]


class Alerter(Protocol):
    """Delivers one alert through some channel.

    A `Protocol`, not an ABC — a backend never needs to import or
    inherit from anything here to satisfy it, same as
    `spork.core.providers.base.Provider`.
    """

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None: ...
