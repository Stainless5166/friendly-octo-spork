"""Failure behavior for SMTP alert delivery."""

from __future__ import annotations

import pytest

from spork.core.alerts.smtp import SmtpAlerter


def test_smtp_username_requires_password() -> None:
    """A misconfigured authenticated relay fails before sending mail."""
    with pytest.raises(ValueError, match="SMTP password is required"):
        SmtpAlerter(
            "smtp.example.test",
            "spork@example.test",
            "operator@example.test",
            username="user",
        ).notify("Test", "Body")
