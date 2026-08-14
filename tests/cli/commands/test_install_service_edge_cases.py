"""Failure/edge-case tests for `spork install-service` (docs/DESIGN.md §14).

Companion to test_install_service.py's acceptance tests. A fake
`systemctl` script prepended onto $PATH proves the real success path
(exit 0, both messages printed) without needing an actual systemd
session — this sandbox has none (test_install_service.py's own
acceptance tests confirm the real failure mode directly).
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path


def _run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spork.cli.main", *args],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _install_fake_systemctl(bin_dir: Path) -> None:
    fake = bin_dir / "systemctl"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)


def test_install_service_reports_success_when_systemctl_succeeds(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install_fake_systemctl(bin_dir)

    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = _run("install-service", env=env)

    assert result.returncode == 0
    assert "Installed unit file" in result.stdout
    assert "Enabled and started sporkd" in result.stdout


def test_install_service_no_enable_now_skips_the_enable_message(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install_fake_systemctl(bin_dir)

    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = _run("install-service", "--no-enable-now", env=env)

    assert result.returncode == 0
    assert "Run `systemctl --user enable --now sporkd`" in result.stdout
