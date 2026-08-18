#!/usr/bin/env python3
"""Send a controlled acceptance message through the configured SMTP relay."""

from __future__ import annotations

import argparse
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries, making the selected file authoritative."""
    if not path.is_file():
        raise FileNotFoundError(f"environment file not found: {path}")
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key.strip()] = value


def _required(name: str) -> str:
    """Return one configured value or fail with the name safe to show to an operator."""
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"missing required setting: {name}")
    return value


def _as_bool(value: str) -> bool:
    """Interpret the conventional boolean spellings used by the acceptance `.env`."""
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    """Parse overrides, send one message, and print only non-secret delivery metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--to", help="recipient; defaults to SMTP_RECIPIENT")
    parser.add_argument("--from", dest="sender", help="sender; defaults to SMTP_SENDER")
    parser.add_argument("--subject", default="Spork live JMAP write acceptance")
    parser.add_argument("--body", default="Controlled acceptance message for Spork.\n")
    args = parser.parse_args()

    try:
        _load_dotenv(args.env_file)
        host = _required("SMTP_HOST")
        port = int(_required("SMTP_PORT"))
        username = _required("SMTP_USERNAME")
        password = _required("SMTP_PASSWORD")
        sender = args.sender or _required("SMTP_SENDER")
        recipient = args.to or _required("SMTP_RECIPIENT")

        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = args.subject
        message.set_content(args.body)

        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            if _as_bool(os.environ.get("SMTP_STARTTLS", "")):
                smtp.starttls()
                smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        raise SystemExit(f"send failed: {exc}") from exc

    print(f"sent subject={args.subject!r} from={sender!r} to={recipient!r}")


if __name__ == "__main__":
    main()
