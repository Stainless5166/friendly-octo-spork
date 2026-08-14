"""load_config(): the three-tier config.toml merge (docs/DESIGN.md §7.2).

Reads whichever of the three tiers actually exist, deep-merges their
raw dicts in ascending precedence (system default -> user -> enforced,
each later merge's keys winning at the same key rather than replacing
a whole table), then validates the fully-merged dict against
`SporkConfig` exactly once.
"""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pydantic

from spork.core.config.paths import (
    resolve_enforced_config_path,
    resolve_socket_path,
    resolve_system_default_config_paths,
    resolve_user_config_path,
)
from spork.core.config.schema import SporkConfig


class ConfigLoadError(Exception):
    """Raised when config.toml (any tier) can't be resolved to a usable SporkConfig.

    Covers every way loading can fail (malformed TOML, an unreadable
    file, a merged dict that fails `SporkConfig` validation) as one
    type, the same fail-loud-with-one-catchable-type convention as
    `RulesLoadError`/`ProviderLoadError`/`AlerterLoadError`.
    """


def _read_toml(path: Path) -> dict[str, Any]:
    """Parse `path` as TOML; a missing file is zero overrides, not an
    error — every tier is optional. A file that exists but can't be
    read (permissions, e.g.) or doesn't parse is a loud ConfigLoadError,
    never silently treated as "no overrides from this tier.\""""
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ConfigLoadError(f"could not read {path}: {exc}") from exc
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigLoadError(f"invalid TOML in {path}: {exc}") from exc


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge `override` into `base`; `override` wins per-key, recursing
    into nested dicts (TOML tables) rather than replacing a whole
    table wholesale — a user's `[tiering] alert_threshold = 0.6` alone
    doesn't erase whatever else `[tiering]` a lower tier set."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(
    *,
    user_config_path: Path | None = None,
    system_default_config_paths: Sequence[Path] | None = None,
    enforced_config_path: Path | None = None,
) -> SporkConfig:
    """Load and merge all three tiers into one validated `SporkConfig`.

    Every parameter defaults to the real `paths.py` resolution and
    only needs overriding by tests (or a future `--config` CLI flag) —
    production callers call `load_config()` with no arguments. This is
    a normal function-argument override, not an environment variable:
    it doesn't weaken the enforced tier's actual guarantee, which is
    specifically that no *env var* can relocate it (§7.2).
    """
    default_paths = (
        list(system_default_config_paths)
        if system_default_config_paths is not None
        else resolve_system_default_config_paths()
    )
    system_default: dict[str, Any] = {}
    for candidate in default_paths:
        if candidate.exists():
            system_default = _read_toml(candidate)
            break  # first match wins, per XDG_CONFIG_DIRS's own preference order

    user = _read_toml(user_config_path or resolve_user_config_path())
    enforced = _read_toml(enforced_config_path or resolve_enforced_config_path())

    merged = _deep_merge(_deep_merge(system_default, user), enforced)

    try:
        config = SporkConfig.model_validate(merged)
    except pydantic.ValidationError as exc:
        raise ConfigLoadError(f"invalid config: {exc}") from exc

    if config.socket_path is None:
        config = config.model_copy(update={"socket_path": resolve_socket_path()})

    return config


def _flatten_keys(raw: dict[str, Any], prefix: str = "") -> set[str]:
    """Every leaf key in `raw`, as a dotted path — `{"tiering": {"x": 1}}`
    becomes `{"tiering.x"}`. Recurses into nested dicts (TOML tables)
    the same way `_deep_merge()` does, so a path here means exactly
    what `_deep_merge()` treats as one mergeable key.
    """
    paths: set[str] = set()
    for key, value in raw.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            paths |= _flatten_keys(value, path)
        else:
            paths.add(path)
    return paths


def enforced_override_paths(*, enforced_config_path: Path | None = None) -> set[str]:
    """Dotted `SporkConfig` field paths present in the enforced tier
    (docs/DESIGN.md §7.2/§13) — every one is a value `spork config show`
    must flag, since no user-tier edit can change it, regardless of
    whether the user's own config happens to already agree with it.

    Deliberately independent of `load_config()`'s merge (reads only
    the enforced file, not the fully-merged result) — this answers
    "what does the enforced tier itself set," not "what is the final
    effective value," which `load_config()` already answers on its
    own.
    """
    raw = _read_toml(enforced_config_path or resolve_enforced_config_path())
    return _flatten_keys(raw)
