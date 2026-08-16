"""Acceptance tests for SMTP alert delivery."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from spork.core.alerts.smtp import SmtpAlerter


def test_smtp_alerter_sends_urgency_and_url() -> None:
    """SMTP delivery preserves the alert's human-visible context."""
    client = MagicMock()
    with patch("spork.core.alerts.smtp.smtplib.SMTP", return_value=client) as smtp:
        client.__enter__.return_value = client
        SmtpAlerter(
            "smtp.example.test",
            "spork@example.test",
            "operator@example.test",
            username="user",
            password="secret",
        ).notify("Needs review", "Please inspect", url="https://example.test/1", urgency="critical")

    smtp.assert_called_once_with("smtp.example.test", 587, timeout=10.0)
    client.starttls.assert_called_once_with()
    client.login.assert_called_once_with("user", "secret")
    sent = client.send_message.call_args.args[0]
    assert sent["Subject"] == "[critical] Spork: Needs review"
    assert "https://example.test/1" in sent.get_content()


def test_smtp_alerter_can_send_to_local_plaintext_harness() -> None:
    """A local harness can disable TLS and authentication explicitly."""
    client = MagicMock()
    with patch("spork.core.alerts.smtp.smtplib.SMTP", return_value=client):
        client.__enter__.return_value = client
        SmtpAlerter(
            "127.0.0.1",
            "spork@example.test",
            "operator@example.test",
            port=1025,
            starttls=False,
        ).notify("Test", "Body")

    client.starttls.assert_not_called()
    client.login.assert_not_called()
