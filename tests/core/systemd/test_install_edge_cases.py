"""Failure/edge-case tests for spork.core.systemd.install.install_service().

Companion to test_install.py's acceptance tests — covers the unit
file write itself failing (a real OSError, not a systemctl one).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spork.core.systemd.install import InstallServiceError, install_service


def test_install_service_raises_when_the_unit_file_cannot_be_written(tmp_path: Path) -> None:
    """unit_path's parent is an existing regular file, not a
    directory — mkdir(parents=True) fails with a real NotADirectoryError
    (an OSError subclass), wrapped as one InstallServiceError."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    unit_path = blocker / "sporkd.service"

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("systemctl should never be reached")

    with pytest.raises(InstallServiceError, match="could not write"):
        install_service(unit_path=unit_path, runner=runner)
