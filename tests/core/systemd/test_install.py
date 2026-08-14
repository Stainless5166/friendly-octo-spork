"""Acceptance tests for spork.core.systemd.install.install_service() (docs/DESIGN.md §14).

`runner` injected the same way check_unit_status()'s is — no real
systemctl invocation in these tests.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spork.core.systemd.install import InstallServiceError, install_service
from spork.core.systemd.template import UNIT_FILE_CONTENT


def _ok(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")


def test_install_service_writes_the_unit_file_content(tmp_path: Path) -> None:
    unit_path = tmp_path / "systemd" / "user" / "sporkd.service"

    install_service(unit_path=unit_path, runner=_ok)

    assert unit_path.read_text() == UNIT_FILE_CONTENT


def test_install_service_creates_missing_parent_directories(tmp_path: Path) -> None:
    """~/.config/systemd/user/ doesn't exist on a fresh machine —
    install_service() must create it, not fail on it."""
    unit_path = tmp_path / "does" / "not" / "exist" / "sporkd.service"

    install_service(unit_path=unit_path, runner=_ok)

    assert unit_path.exists()


def test_install_service_returns_the_written_path(tmp_path: Path) -> None:
    unit_path = tmp_path / "sporkd.service"

    result = install_service(unit_path=unit_path, runner=_ok)

    assert result == unit_path


def test_install_service_runs_daemon_reload_and_enable_now_by_default(tmp_path: Path) -> None:
    unit_path = tmp_path / "sporkd.service"
    calls: list[list[str]] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return _ok(args)

    install_service(unit_path=unit_path, runner=runner)

    assert ["systemctl", "--user", "daemon-reload"] in calls
    assert ["systemctl", "--user", "enable", "--now", "sporkd"] in calls


def test_install_service_skips_enable_now_when_asked(tmp_path: Path) -> None:
    unit_path = tmp_path / "sporkd.service"
    calls: list[list[str]] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return _ok(args)

    install_service(unit_path=unit_path, enable_now=False, runner=runner)

    assert ["systemctl", "--user", "daemon-reload"] in calls
    assert not any("enable" in call for call in calls)


def test_install_service_raises_when_systemctl_is_not_installed(tmp_path: Path) -> None:
    unit_path = tmp_path / "sporkd.service"

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("systemctl not found")

    with pytest.raises(InstallServiceError):
        install_service(unit_path=unit_path, runner=runner)


def test_install_service_raises_when_daemon_reload_fails(tmp_path: Path) -> None:
    unit_path = tmp_path / "sporkd.service"

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            returncode=1, cmd=args, stderr="Failed to connect to bus: No medium found\n"
        )

    with pytest.raises(InstallServiceError, match="bus"):
        install_service(unit_path=unit_path, runner=runner)


def test_install_service_uses_the_given_unit_name(tmp_path: Path) -> None:
    unit_path = tmp_path / "other.service"
    calls: list[list[str]] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return _ok(args)

    install_service(unit_name="other", unit_path=unit_path, runner=runner)

    assert ["systemctl", "--user", "enable", "--now", "other"] in calls
