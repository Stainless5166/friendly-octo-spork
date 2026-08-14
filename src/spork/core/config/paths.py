"""XDG tier-path resolution for config.toml (docs/DESIGN.md §7.2/§6.4).

Pure functions against environment variables only — no TOML parsing,
no pydantic, no filesystem existence checks. `loader.py` decides which
of these candidate paths actually exist and reads them; this module's
only job is computing where to look, per the [XDG Base Directory
Specification v0.8](https://specifications.freedesktop.org/basedir/latest/)
plus one path outside the XDG search entirely (the enforced tier,
deliberately not relocatable by any environment variable).
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

_APP_DIR_NAME = "spork"
_CONFIG_FILENAME = "config.toml"
_SOCKET_FILENAME = "sporkd.sock"
_SECRETSPEC_FILENAME = "secretspec.toml"
_SYSTEMD_USER_DIR_NAME = "systemd/user"

# Outside the XDG search entirely, and deliberately so — the whole
# point of the enforced tier is that no environment variable a user
# controls (XDG_CONFIG_DIRS included) can relocate it, mirroring
# git's fixed /etc/gitconfig system scope.
ENFORCED_CONFIG_PATH = Path("/etc/spork/enforced.toml")

_DEFAULT_CONFIG_DIRS = "/etc/xdg"
_FALLBACK_RUNTIME_DIR_TEMPLATE = "/tmp/spork-{uid}"


def _env_absolute_path(name: str) -> Path | None:
    """Read `name` from the environment, honoring the XDG spec's rule
    that an unset, empty, or relative value must be treated the same
    as not set at all — never passed through as-is."""
    value = os.environ.get(name, "")
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        return None
    return path


def resolve_user_config_path() -> Path:
    """`$XDG_CONFIG_HOME/spork/config.toml`.

    Falls back to `$HOME/.config/spork/config.toml` — the spec's own
    documented default for `XDG_CONFIG_HOME` — when unset, empty, or
    relative.
    """
    base = _env_absolute_path("XDG_CONFIG_HOME") or Path.home() / ".config"
    return base / _APP_DIR_NAME / _CONFIG_FILENAME


def resolve_system_default_config_paths() -> list[Path]:
    """One candidate per `$XDG_CONFIG_DIRS` entry, in the spec's own
    preference order (first-listed = most important — the order
    `load_config()` relies on for first-match-wins).

    Falls back to `["/etc/xdg"]` — the spec's documented default —
    when the variable is unset or empty. Relative entries are invalid
    per the spec and are silently dropped rather than passed through.
    """
    raw = os.environ.get("XDG_CONFIG_DIRS", "") or _DEFAULT_CONFIG_DIRS
    dirs = [Path(entry) for entry in raw.split(":") if entry and Path(entry).is_absolute()]
    if not dirs:
        dirs = [Path(_DEFAULT_CONFIG_DIRS)]
    return [d / _APP_DIR_NAME / _CONFIG_FILENAME for d in dirs]


def resolve_enforced_config_path() -> Path:
    """Always `/etc/spork/enforced.toml` — see `ENFORCED_CONFIG_PATH`."""
    return ENFORCED_CONFIG_PATH


def resolve_socket_path() -> Path:
    """`$XDG_RUNTIME_DIR/spork/sporkd.sock`.

    Falls back to `/tmp/spork-<uid>/sporkd.sock` with a warning when
    `XDG_RUNTIME_DIR` is unset, empty, or relative — the spec
    explicitly declines to mandate a default here and pushes fallback
    behavior onto the application ("fall back to a replacement
    directory with similar capabilities and print a warning").
    """
    base = _env_absolute_path("XDG_RUNTIME_DIR")
    if base is not None:
        return base / _APP_DIR_NAME / _SOCKET_FILENAME

    warnings.warn(
        "XDG_RUNTIME_DIR is not set (or is empty/relative); falling back to "
        "/tmp/spork-<uid>/ for the control socket. Expected outside a systemd "
        "user session, but that fallback directory won't be cleaned up "
        "automatically on logout the way $XDG_RUNTIME_DIR would be.",
        stacklevel=2,
    )
    fallback_dir = Path(_FALLBACK_RUNTIME_DIR_TEMPLATE.format(uid=os.getuid()))
    return fallback_dir / _SOCKET_FILENAME


def resolve_secretspec_path() -> Path:
    """`$XDG_CONFIG_HOME/spork/secretspec.toml`.

    Colocated with `config.toml` under the same per-user config
    directory (docs/DESIGN.md §7.3) rather than a separate convention
    — this is the *installed* manifest `spork doctor`'s secrets check
    resolves against, distinct from the repo-root `secretspec.toml`
    that only documents what's needed (§7.1). Same fallback as
    `resolve_user_config_path()` when `XDG_CONFIG_HOME` is unset,
    empty, or relative.
    """
    base = _env_absolute_path("XDG_CONFIG_HOME") or Path.home() / ".config"
    return base / _APP_DIR_NAME / _SECRETSPEC_FILENAME


def resolve_user_unit_path(unit_name: str = "sporkd") -> Path:
    """`$XDG_CONFIG_HOME/systemd/user/<unit_name>.service`.

    systemd's own real user-unit search path (docs/DESIGN.md §14) —
    not a spork-specific subdirectory the way `config.toml`/
    `secretspec.toml` get one, since this path has to match what
    `systemctl --user` itself looks for. Same fallback as
    `resolve_user_config_path()` when `XDG_CONFIG_HOME` is unset,
    empty, or relative.
    """
    base = _env_absolute_path("XDG_CONFIG_HOME") or Path.home() / ".config"
    return base / _SYSTEMD_USER_DIR_NAME / f"{unit_name}.service"
