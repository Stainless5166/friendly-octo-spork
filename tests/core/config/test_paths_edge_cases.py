"""Failure/edge-case tests for spork.core.config.paths.

Companion to test_paths.py's acceptance tests — covers the XDG spec's
"unset, empty, or relative counts as not set" rule, XDG_CONFIG_DIRS's
list-shaped footguns (mixed relative/absolute entries, empty segments
from "::" or a trailing colon), and resolve_socket_path()'s fallback +
warning when XDG_RUNTIME_DIR is genuinely absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.config.paths import (
    resolve_secretspec_path,
    resolve_socket_path,
    resolve_system_default_config_paths,
    resolve_user_config_path,
    resolve_user_unit_path,
)


@pytest.mark.parametrize("xdg_config_home", ["relative/path", "", "./here"])
def test_resolve_user_config_path_treats_relative_or_empty_as_unset(
    monkeypatch: pytest.MonkeyPatch, xdg_config_home: str
) -> None:
    """A relative XDG_CONFIG_HOME is invalid per the spec — treated the
    same as unset, not passed through as-is."""
    monkeypatch.setenv("XDG_CONFIG_HOME", xdg_config_home)
    monkeypatch.setenv("HOME", "/home/will")

    result = resolve_user_config_path()

    assert result == Path("/home/will/.config/spork/config.toml")


def test_resolve_system_default_config_paths_drops_relative_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relative entry mixed into XDG_CONFIG_DIRS is dropped; the
    absolute entries around it are kept, in their original order."""
    monkeypatch.setenv("XDG_CONFIG_DIRS", "/etc/xdg:relative/dir:/usr/local/etc/xdg")

    result = resolve_system_default_config_paths()

    assert result == [
        Path("/etc/xdg/spork/config.toml"),
        Path("/usr/local/etc/xdg/spork/config.toml"),
    ]


@pytest.mark.parametrize("xdg_config_dirs", ["/a::/b", "/a:/b:", ":/a:/b"])
def test_resolve_system_default_config_paths_skips_empty_segments(
    monkeypatch: pytest.MonkeyPatch, xdg_config_dirs: str
) -> None:
    """A doubled or leading/trailing colon produces an empty segment —
    skipped rather than treated as "." or raising."""
    monkeypatch.setenv("XDG_CONFIG_DIRS", xdg_config_dirs)

    result = resolve_system_default_config_paths()

    assert result == [
        Path("/a/spork/config.toml"),
        Path("/b/spork/config.toml"),
    ]


def test_resolve_system_default_config_paths_falls_back_when_entirely_relative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every entry relative: none survive, so the spec's own default
    (/etc/xdg) applies, exactly as if the variable were unset."""
    monkeypatch.setenv("XDG_CONFIG_DIRS", "relative/one:relative/two")

    result = resolve_system_default_config_paths()

    assert result == [Path("/etc/xdg/spork/config.toml")]


def test_resolve_socket_path_falls_back_and_warns_when_xdg_runtime_dir_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No XDG_RUNTIME_DIR: falls back to /tmp/spork-<uid>/sporkd.sock
    and warns, per the spec's own "fall back... and print a warning"
    guidance for this specific variable."""
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr("os.getuid", lambda: 1000)

    with pytest.warns(UserWarning, match="XDG_RUNTIME_DIR"):
        result = resolve_socket_path()

    assert result == Path("/tmp/spork-1000/sporkd.sock")


@pytest.mark.parametrize("xdg_runtime_dir", ["relative/run", ""])
def test_resolve_socket_path_falls_back_for_relative_or_empty_too(
    monkeypatch: pytest.MonkeyPatch, xdg_runtime_dir: str
) -> None:
    """Relative or empty XDG_RUNTIME_DIR is invalid per the spec — same
    fallback-and-warn treatment as genuinely unset."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", xdg_runtime_dir)
    monkeypatch.setattr("os.getuid", lambda: 1000)

    with pytest.warns(UserWarning, match="XDG_RUNTIME_DIR"):
        result = resolve_socket_path()

    assert result == Path("/tmp/spork-1000/sporkd.sock")


@pytest.mark.parametrize("xdg_config_home", ["relative/path", "", "./here"])
def test_resolve_secretspec_path_treats_relative_or_empty_as_unset(
    monkeypatch: pytest.MonkeyPatch, xdg_config_home: str
) -> None:
    """Same "relative/empty counts as unset" rule as
    resolve_user_config_path()."""
    monkeypatch.setenv("XDG_CONFIG_HOME", xdg_config_home)
    monkeypatch.setenv("HOME", "/home/will")

    result = resolve_secretspec_path()

    assert result == Path("/home/will/.config/spork/secretspec.toml")


@pytest.mark.parametrize("xdg_config_home", ["relative/path", "", "./here"])
def test_resolve_user_unit_path_treats_relative_or_empty_as_unset(
    monkeypatch: pytest.MonkeyPatch, xdg_config_home: str
) -> None:
    """Same "relative/empty counts as unset" rule as
    resolve_user_config_path()."""
    monkeypatch.setenv("XDG_CONFIG_HOME", xdg_config_home)
    monkeypatch.setenv("HOME", "/home/will")

    result = resolve_user_unit_path()

    assert result == Path("/home/will/.config/systemd/user/sporkd@.service")
