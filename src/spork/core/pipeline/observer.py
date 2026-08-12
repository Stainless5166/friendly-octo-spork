"""PipelineObserver: combined per-message tracing + alerting (docs/DESIGN.md §12.2).

The "combine logging and alerting into the same structure" decision —
every alert-worthy pipeline outcome is also trace-worthy (an alert is
never sent without a corresponding log record explaining why), so one
object gives modules a single call site instead of two independent
ones to remember. Composes `Alerter` (§12.1) rather than replacing it:
a future real desktop-notification backend still only needs to satisfy
`Alerter`, never this class.
"""

from __future__ import annotations

import logging

from spork.core.alerts.base import Alerter, AlertUrgency


class PipelineObserver:
    """Bundles correlation-ID-tagged tracing with alert delegation.

    Constructed once per `build_default_pipeline()`/
    `build_tier2_pipeline()` call, the same way `state_db` is — a
    service, injected into whichever modules need it, never carried in
    `MessageMeta`/`Tier2Meta` (those hold per-message data, not
    services). `correlation_id` is an explicit argument on every call
    rather than module-global state (a `contextvars.ContextVar`) so
    nothing here assumes messages are processed one at a time.
    """

    def __init__(self, alerter: Alerter, logger: logging.Logger | None = None) -> None:
        self._alerter = alerter
        self._logger = logger or logging.getLogger("spork.pipeline")

    def trace(self, correlation_id: str, event: str, **fields: object) -> None:
        """Log `event`, with `correlation_id` and any `fields` attached
        to the record's `extra` — the same mechanism
        `logging.LoggerAdapter` uses internally (Python Logging
        Cookbook), so one message's lines share a greppable ID without
        a global `ContextVar`."""
        self._logger.info(event, extra={"correlation_id": correlation_id, **fields})

    def alert(
        self,
        correlation_id: str,
        title: str,
        body: str,
        *,
        url: str | None = None,
        urgency: AlertUrgency = "normal",
    ) -> None:
        """Trace this alert, then deliver it via the injected `Alerter`
        — the one call an alert-firing pipeline module makes."""
        self.trace(correlation_id, title, body=body, urgency=urgency)
        self._alerter.notify(title, body, url=url, urgency=urgency)
