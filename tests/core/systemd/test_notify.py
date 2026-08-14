"""Acceptance tests for spork.core.systemd.notify.notify() (docs/DESIGN.md §14).

Exercised against a real AF_UNIX SOCK_DGRAM socket bound in tmp_path —
the actual sd_notify(3) wire protocol, not a mock. No systemd/dbus
session needed: sd_notify is just a single datagram write to whatever
path $NOTIFY_SOCKET names.
"""

from __future__ import annotations

import socket
from pathlib import Path

from spork.core.systemd.notify import notify


def test_notify_sends_the_given_state_to_notify_socket(tmp_path: Path) -> None:
    """A real datagram, real bytes, real path — read back off a real
    bound socket."""
    socket_path = tmp_path / "notify.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind(str(socket_path))
    try:
        result = notify("READY=1", environ={"NOTIFY_SOCKET": str(socket_path)})

        received, _ = server.recvfrom(1024)
    finally:
        server.close()

    assert result is True
    assert received == b"READY=1"


def test_notify_returns_false_and_sends_nothing_when_notify_socket_is_unset() -> None:
    """The common case: not running under a Type=notify unit at all —
    a safe no-op, never an error."""
    result = notify("READY=1", environ={})

    assert result is False


def test_notify_prefers_an_explicit_socket_path_over_the_environ(tmp_path: Path) -> None:
    """socket_path, when given, wins over $NOTIFY_SOCKET — lets tests
    (and any future caller) target a specific socket without touching
    the environment."""
    socket_path = tmp_path / "explicit.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind(str(socket_path))
    try:
        result = notify(
            "READY=1",
            socket_path=str(socket_path),
            environ={"NOTIFY_SOCKET": "/should/not/be/used.sock"},
        )

        received, _ = server.recvfrom(1024)
    finally:
        server.close()

    assert result is True
    assert received == b"READY=1"


def test_notify_supports_the_abstract_namespace_form(tmp_path: Path) -> None:
    """A leading '@' names a Linux abstract-namespace socket (no
    filesystem entry, real systemd behavior when $NOTIFY_SOCKET starts
    with '@') — translated to the real '\\0'-prefixed address."""
    address = "\0spork-test-notify-abstract"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind(address)
    try:
        result = notify("READY=1", socket_path="@spork-test-notify-abstract")

        received, _ = server.recvfrom(1024)
    finally:
        server.close()

    assert result is True
    assert received == b"READY=1"
