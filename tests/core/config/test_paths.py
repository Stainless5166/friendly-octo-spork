"""Acceptance tests for spork.core.config.paths (docs/DESIGN.md §7.2/§6.4).

Pure path-resolution logic against environment variables — no TOML
parsing, no pydantic, no filesystem existence checks (that's
loader.py's job: paths.py only ever computes *candidate* paths).
Every test sets the relevant XDG_* vars explicitly via monkeypatch
rather than relying on the real environment or $HOME, so results are
deterministic regardless of what machine/container this runs on.

Path-shape coverage is deliberately broad per the standing instruction
to test against realistic, valid Linux paths — not just one tidy
example each: spaces, unicode, deep nesting, root-level single-segment
paths, trailing slashes, and paths with dashes/underscores/digits are
all real, valid POSIX paths a user's environment could legitimately
contain.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.config.paths import (
    resolve_enforced_config_path,
    resolve_secretspec_path,
    resolve_socket_path,
    resolve_system_default_config_paths,
    resolve_user_config_path,
    resolve_user_unit_path,
)

# A spread of realistic, valid absolute Linux paths — not just one
# tidy example. Covers: plain, spaces, unicode, deep nesting,
# root-level single-segment, trailing slash, dashes/underscores/digits.
VALID_ABSOLUTE_PATHS = [
    "/home/will/.config",
    "/home/will space/.config",
    "/home/wíll/.config",
    "/a/b/c/d/e/f/g/h/i/j/config",
    "/config",
    "/home/will/.config/",
    "/mnt/data-01_2/configs",
    "/home/日本語/.config",
]


@pytest.mark.parametrize("xdg_config_home", VALID_ABSOLUTE_PATHS)
def test_resolve_user_config_path_uses_xdg_config_home_when_set(
    monkeypatch: pytest.MonkeyPatch, xdg_config_home: str
) -> None:
    """XDG_CONFIG_HOME/spork/config.toml, for a spread of valid paths."""
    monkeypatch.setenv("XDG_CONFIG_HOME", xdg_config_home)

    result = resolve_user_config_path()

    assert result == Path(xdg_config_home) / "spork" / "config.toml"


def test_resolve_user_config_path_falls_back_to_home_dot_config_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No XDG_CONFIG_HOME: falls back to $HOME/.config/spork/config.toml,
    the spec's documented default."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", "/home/will")

    result = resolve_user_config_path()

    assert result == Path("/home/will/.config/spork/config.toml")


@pytest.mark.parametrize(
    "xdg_config_dirs",
    [
        "/etc/xdg",
        "/etc/xdg:/usr/local/etc/xdg",
        "/etc/xdg:/etc/xdg2:/etc/xdg3",
        "/etc/my xdg:/etc/other",
        "/etc/日本語/xdg",
    ],
)
def test_resolve_system_default_config_paths_uses_xdg_config_dirs_in_order(
    monkeypatch: pytest.MonkeyPatch, xdg_config_dirs: str
) -> None:
    """Every entry in XDG_CONFIG_DIRS becomes a candidate, in the same
    preference order the spec assigns the variable (first = most
    important) — loader.py relies on this order for first-match-wins."""
    monkeypatch.setenv("XDG_CONFIG_DIRS", xdg_config_dirs)

    result = resolve_system_default_config_paths()

    expected = [Path(entry) / "spork" / "config.toml" for entry in xdg_config_dirs.split(":")]
    assert result == expected


def test_resolve_system_default_config_paths_falls_back_to_etc_xdg_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No XDG_CONFIG_DIRS: falls back to the spec's documented default,
    /etc/xdg."""
    monkeypatch.delenv("XDG_CONFIG_DIRS", raising=False)

    result = resolve_system_default_config_paths()

    assert result == [Path("/etc/xdg/spork/config.toml")]


def test_resolve_enforced_config_path_is_always_etc_spork_enforced_toml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fixed, regardless of any XDG_* environment variable — the whole
    point of the enforced tier is that it can't be relocated by an env
    var (docs/DESIGN.md §7.2)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/attacker/.config")
    monkeypatch.setenv("XDG_CONFIG_DIRS", "/home/attacker/fake-etc")

    result = resolve_enforced_config_path()

    assert result == Path("/etc/spork/enforced.toml")


@pytest.mark.parametrize("xdg_runtime_dir", VALID_ABSOLUTE_PATHS)
def test_resolve_socket_path_uses_xdg_runtime_dir_when_set(
    monkeypatch: pytest.MonkeyPatch, xdg_runtime_dir: str
) -> None:
    """XDG_RUNTIME_DIR/spork/sporkd.sock, for a spread of valid paths."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", xdg_runtime_dir)

    result = resolve_socket_path()

    assert result == Path(xdg_runtime_dir) / "spork" / "sporkd.sock"


@pytest.mark.parametrize("xdg_config_home", VALID_ABSOLUTE_PATHS)
def test_resolve_secretspec_path_uses_xdg_config_home_when_set(
    monkeypatch: pytest.MonkeyPatch, xdg_config_home: str
) -> None:
    """XDG_CONFIG_HOME/spork/secretspec.toml — colocated with
    config.toml (docs/DESIGN.md §7.3), not a separate convention."""
    monkeypatch.setenv("XDG_CONFIG_HOME", xdg_config_home)

    result = resolve_secretspec_path()

    assert result == Path(xdg_config_home) / "spork" / "secretspec.toml"


def test_resolve_secretspec_path_falls_back_to_home_dot_config_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No XDG_CONFIG_HOME: falls back to $HOME/.config/spork/secretspec.toml,
    same fallback resolve_user_config_path() uses."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", "/home/will")

    result = resolve_secretspec_path()

    assert result == Path("/home/will/.config/spork/secretspec.toml")


@pytest.mark.parametrize("xdg_config_home", VALID_ABSOLUTE_PATHS)
def test_resolve_user_unit_path_uses_xdg_config_home_when_set(
    monkeypatch: pytest.MonkeyPatch, xdg_config_home: str
) -> None:
    """XDG_CONFIG_HOME/systemd/user/sporkd.service — systemd's own real
    user-unit search path (docs/DESIGN.md §14), not spork's own
    subdirectory the way config.toml/secretspec.toml are."""
    monkeypatch.setenv("XDG_CONFIG_HOME", xdg_config_home)

    result = resolve_user_unit_path()

    assert result == Path(xdg_config_home) / "systemd" / "user" / "sporkd.service"


def test_resolve_user_unit_path_falls_back_to_home_dot_config_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No XDG_CONFIG_HOME: falls back to
    $HOME/.config/systemd/user/sporkd.service — systemd's own
    documented default search path."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", "/home/will")

    result = resolve_user_unit_path()

    assert result == Path("/home/will/.config/systemd/user/sporkd.service")


def test_resolve_user_unit_path_accepts_a_different_unit_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """unit_name is a parameter, not hardcoded — install_service()/
    check_unit_status() (docs/DESIGN.md §14) both default it to
    "sporkd" but don't need to hardcode it in this resolver too."""
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/will/.config")

    result = resolve_user_unit_path("other-name")

    assert result == Path("/home/will/.config/systemd/user/other-name.service")
