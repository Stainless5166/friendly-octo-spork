"""Acceptance tests for the real desktop-notification Alerter backend
(docs/DESIGN.md §12.1, docs/ROADMAP.md M4).

`notify-send(1)` wraps `org.freedesktop.Notifications` over the
session D-Bus — no new DBus library dependency, per the settled
design. Same injectable-`runner` DI-for-subprocess pattern
`spork.core.systemd.install.install_service()` already uses, so no
test here ever invokes a real `notify-send`.
"""

from __future__ import annotations

import subprocess

from spork.core.alerts.desktop import DesktopAlerter


def _completed(returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr="")


def test_desktop_alerter_calls_notify_send_with_title_body_and_urgency() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return _completed()

    DesktopAlerter(runner=runner).notify("Needs review", "Please inspect", urgency="critical")

    assert calls == [["notify-send", "-u", "critical", "Needs review", "Please inspect"]]


def test_desktop_alerter_appends_the_url_to_the_body() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return _completed()

    DesktopAlerter(runner=runner).notify("Title", "Body", url="https://example.test/1")

    assert calls[0][-1] == "Body\n\nhttps://example.test/1"


def test_desktop_alerter_falls_back_to_logging_when_notify_send_is_missing() -> None:
    """No `notify-send` binary (not installed) — never raises, degrades to the fallback."""

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("notify-send")

    delivered: list[tuple[str, str]] = []

    class _FallbackAlerter:
        def notify(
            self, title: str, body: str, *, url: str | None = None, urgency: str = "normal"
        ) -> None:
            delivered.append((title, body))

    DesktopAlerter(runner=runner, fallback=_FallbackAlerter()).notify("Title", "Body")

    assert delivered == [("Title", "Body")]


def test_desktop_alerter_falls_back_to_logging_when_notify_send_fails() -> None:
    """A non-zero exit (e.g. no session D-Bus bus, a headless/SSH-only login)

    degrades to the fallback instead of taking sporkd down."""

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, argv, stderr="Cannot autolaunch D-Bus")

    delivered: list[tuple[str, str]] = []

    class _FallbackAlerter:
        def notify(
            self, title: str, body: str, *, url: str | None = None, urgency: str = "normal"
        ) -> None:
            delivered.append((title, body))

    DesktopAlerter(runner=runner, fallback=_FallbackAlerter()).notify("Title", "Body")

    assert delivered == [("Title", "Body")]


def test_desktop_alerter_defaults_to_a_real_logging_alerter_fallback(caplog) -> None:  # type: ignore[no-untyped-def]
    """No fallback given: still degrades gracefully, using LoggingAlerter
    (the same v1 backend) rather than losing the alert entirely."""

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("notify-send")

    with caplog.at_level("WARNING"):
        DesktopAlerter(runner=runner).notify("Title", "Body")

    assert "Title: Body" in caplog.text
