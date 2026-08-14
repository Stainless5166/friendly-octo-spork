"""Failure/edge-case tests for spork.core.systemd.unit.check_unit_status().

Companion to test_unit.py's acceptance tests — the default unit_path
actually ties to resolve_user_unit_path(), and a systemctl call that
hangs (subprocess.TimeoutExpired, a real SubprocessError subclass)
gets the same "unknown" treatment as a missing binary.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spork.core.systemd.unit import check_unit_status


def test_check_unit_status_default_unit_path_uses_resolve_user_unit_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No unit_path override: installed reflects the real
    resolve_user_unit_path() location, not some other path."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    unit_file = tmp_path / "systemd" / "user" / "sporkd.service"
    unit_file.parent.mkdir(parents=True)
    unit_file.write_text("[Unit]\n")

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, returncode=0, stdout="active\n", stderr="")

    status = check_unit_status(runner=runner)

    assert status.installed is True


def test_check_unit_status_reports_unknown_on_a_timeout(tmp_path: Path) -> None:
    """systemctl hanging (subprocess.TimeoutExpired) gets the same
    "couldn't ask" treatment as a missing binary, never propagates."""
    unit_path = tmp_path / "sporkd.service"
    unit_path.write_text("[Unit]\n")

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=args, timeout=5)

    status = check_unit_status(unit_path=unit_path, runner=runner)

    assert status.enabled == "unknown"
    assert status.active == "unknown"
