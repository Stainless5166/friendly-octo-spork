"""SMTP alert delivery for burn-in and unattended deployments."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from spork.core.alerts.base import AlertUrgency


class SmtpAlerter:
    """Send one alert as a plain-text email over authenticated SMTP."""

    def __init__(
        self,
        host: str,
        sender: str,
        recipient: str,
        *,
        port: int = 587,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 10.0,
        starttls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._recipient = recipient
        self._username = username
        self._password = password
        self._timeout = timeout
        self._starttls = starttls

    def notify(
        self, title: str, body: str, *, url: str | None = None, urgency: AlertUrgency = "normal"
    ) -> None:
        """Deliver an alert and close the SMTP session even on failure."""
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = self._recipient
        message["Subject"] = f"[{urgency}] Spork: {title}"
        message.set_content(body if url is None else f"{body}\n\n{url}")

        if self._username is not None and self._password is None:
            raise ValueError("SMTP password is required when SMTP username is configured")
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as client:
            if self._starttls:
                client.starttls()
            if self._username is not None:
                assert self._password is not None
                client.login(self._username, self._password)
            client.send_message(message)
