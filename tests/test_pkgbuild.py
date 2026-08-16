"""Sanity checks for the Arch Linux `PKGBUILD` (docs/DESIGN.md §14, M6).

`makepkg`/`pacman` aren't available in this sandbox (confirmed: no
Arch tooling on this dev/CI machine), so a real `makepkg -si` build
can't be exercised here — the same "genuinely can't be tested honestly
in this environment" situation `JmapClient.connect()` is in, just for
a shell script rather than a Python function. What *is* checkable
without Arch tooling: the file is syntactically valid bash
(`bash -n`, a real parse, not a guess), declares the fields `makepkg`
requires, and installs the same tracked unit file `spork install-service`
does — not a second, divergent definition.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PKGBUILD = REPO_ROOT / "PKGBUILD"


def test_pkgbuild_exists() -> None:
    assert PKGBUILD.exists(), f"{PKGBUILD} does not exist"


def test_pkgbuild_is_syntactically_valid_bash() -> None:
    """bash -n parses the script without executing it — a real syntax
    check, not a guess."""
    result = subprocess.run(
        ["bash", "-n", str(PKGBUILD)], capture_output=True, text=True, timeout=10
    )

    assert result.returncode == 0, result.stderr


def test_pkgbuild_declares_the_fields_makepkg_requires() -> None:
    text = PKGBUILD.read_text()

    for field in ("pkgname=", "pkgver=", "pkgrel=", "arch=", "license=", "pkgdesc="):
        assert field in text, f"missing {field}"


def test_pkgbuild_has_build_and_package_functions() -> None:
    text = PKGBUILD.read_text()

    assert "build() {" in text
    assert "package() {" in text


def test_pkgbuild_installs_the_tracked_systemd_unit_file() -> None:
    """The same systemd/sporkd@.service spork install-service embeds a
    copy of (spork.core.systemd.template.UNIT_FILE_CONTENT) — one unit
    definition, two install paths, not a second divergent one."""
    text = PKGBUILD.read_text()

    assert "systemd/sporkd@.service" in text
    assert "/usr/lib/systemd/user/sporkd@.service" in text


def test_pkgbuild_pkgver_matches_pyproject(tmp_path: Path) -> None:
    """No drift between the Arch package version and pyproject.toml's
    own — a real, easy-to-forget-to-bump mismatch."""
    import tomllib

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    project_version = pyproject["project"]["version"]

    text = PKGBUILD.read_text()
    pkgver_line = next(line for line in text.splitlines() if line.startswith("pkgver="))
    pkgver = pkgver_line.split("=", 1)[1].strip()

    assert pkgver == project_version
