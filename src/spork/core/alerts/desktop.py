"""DesktopAlerter: the real Linux desktop-notification backend (docs/DESIGN.md §12.1).

Wraps `notify-send(1)`, which itself talks to
`org.freedesktop.Notifications` over the session D-Bus — no new DBus
library dependency, confirmed against `notify-send(1)` before settling
this shape (§12.1). `AlertUrgency`'s three levels pass straight
through as `-u`; the spec was chosen to match exactly for this reason.

Graceful degrade (docs/ROADMAP.md M4): a headless/SSH-only login has
no session D-Bus bus, and `notify-send` itself may not even be
installed. Either failure mode falls back to logging rather than
raising — `sporkd` keeps running, the alert isn't lost, it just
doesn't pop up. `notify()` never propagates an exception for an
environmental delivery failure; a misuse bug in this module itself
(a real `TypeError`, say) still isn't swallowed, since the `except`
below only catches the specific subprocess failure modes this
degrade is actually about.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable

from spork.core.alerts.base import Alerter, AlertUrgency
from spork.core.alerts.log import LoggingAlerter

_Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class DesktopAlerter:
    """Delivers a real Linux desktop notification via `notify-send(1)`.

    `runner` is injected the same DI-for-subprocess pattern
    `spork.core.systemd.install.install_service()` already uses, so
    tests never invoke a real `notify-send`. `fallback` defaults to a
    fresh `LoggingAlerter` — the same v1 backend this one supersedes —
    so a degrade never means "alert silently lost," only "alert didn't
    pop up."
    """

    def __init__(
        self,
        *,
        runner: _Runner = subprocess.run,
        fallback: Alerter | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._runner = runner
        self._fallback = fallback if fallback is not None else LoggingAlerter()
        self._timeout = timeout
        self._logger = logging.getLogger(__name__)

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        message = body if url is None else f"{body}\n\n{url}"
        try:
            self._runner(
                ["notify-send", "-u", urgency, title, message],
                check=True,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as exc:
            self._logger.warning(
                "desktop notification unavailable (%s); falling back to log delivery", exc
            )
            self._fallback.notify(title, body, url=url, urgency=urgency)
