"""Failure/edge-case tests for spork.core.systemd.notify.notify().

Companion to test_notify.py's acceptance tests — covers reading the
real os.environ by default, and the case notify() is actually built
for: a readiness signal called from the daemon's startup path, where
a socket that's vanished or refuses the connection must never take the
caller down.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.systemd.notify import notify


def test_notify_reads_the_real_os_environ_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No `environ` override: falls back to the real process
    environment, same as every other `environ.get(...)`-style default
    in this codebase."""
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)

    result = notify("READY=1")

    assert result is False


def test_notify_returns_false_when_the_socket_path_does_not_exist(tmp_path: Path) -> None:
    """A stale or never-created $NOTIFY_SOCKET path (nothing listening)
    must not crash sporkd's startup over what is, at worst, a
    best-effort readiness signal."""
    missing = tmp_path / "does-not-exist.sock"

    result = notify("READY=1", socket_path=str(missing))

    assert result is False


def test_notify_returns_false_when_the_state_is_empty() -> None:
    """An empty state string is a no-op the same way an unset socket
    is — nothing meaningful to send."""
    result = notify("", environ={"NOTIFY_SOCKET": "/nonexistent.sock"})

    assert result is False
