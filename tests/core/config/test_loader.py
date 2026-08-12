"""Acceptance tests for spork.core.config.loader.load_config() (docs/DESIGN.md §7.2).

`load_config()` takes explicit path overrides for all three tiers
(mirroring `now: Callable` elsewhere in this codebase) rather than
requiring tests to write to real /etc or monkeypatch XDG env vars for
the enforced tier specifically — the enforced tier's whole point is
that no *environment variable* can relocate it, which is orthogonal to
tests injecting a path directly through a normal function argument.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.config.loader import ConfigLoadError, load_config

_MINIMAL_TOML = """
rules_path = "/home/will/.config/spork/rules.toml"
db_path = "/home/will/.local/share/spork/state.sqlite3"
socket_path = "/home/will/.local/state/spork/sporkd.sock"

[provider]
spec = "spork.core.providers.file.provider:FileProvider"

[llm]
spec = "spork.core.llm.clients.recorded:RecordedLLMClient"

[alerts]
spec = "spork.core.alerts.log:LoggingAlerter"
"""


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_load_config_reads_the_user_tier_alone(tmp_path: Path) -> None:
    """No system-default or enforced file present: the user tier alone,
    fully specified, is enough."""
    user_path = _write(tmp_path / "user" / "config.toml", _MINIMAL_TOML)
    missing_default = tmp_path / "default" / "config.toml"
    missing_enforced = tmp_path / "enforced.toml"

    config = load_config(
        user_config_path=user_path,
        system_default_config_paths=[missing_default],
        enforced_config_path=missing_enforced,
    )

    assert config.provider.spec == "spork.core.providers.file.provider:FileProvider"
    assert config.rules_path == Path("/home/will/.config/spork/rules.toml")


def test_load_config_merges_three_tiers_per_key_not_whole_file(tmp_path: Path) -> None:
    """system-default provides the backend specs and most tiering
    fields; user overrides only tiering.alert_threshold — both survive
    in the merged result, proving per-key merge, not whole-file
    replace."""
    system_default_path = _write(
        tmp_path / "default" / "config.toml",
        _MINIMAL_TOML + "\n[tiering]\nalert_threshold = 0.55\ndaily_call_budget = 100\n",
    )
    user_path = _write(tmp_path / "user" / "config.toml", "[tiering]\nalert_threshold = 0.7\n")
    missing_enforced = tmp_path / "enforced.toml"

    config = load_config(
        user_config_path=user_path,
        system_default_config_paths=[system_default_path],
        enforced_config_path=missing_enforced,
    )

    assert config.tiering.alert_threshold == 0.7  # user's override
    assert config.tiering.daily_call_budget == 100  # system-default's, untouched
    assert (
        config.provider.spec == "spork.core.providers.file.provider:FileProvider"
    )  # system-default's


def test_load_config_enforced_tier_overrides_user_tier(tmp_path: Path) -> None:
    """The concrete exit-criterion test: a value in the enforced tier
    can't be overridden by the user's own config.toml."""
    user_path = _write(
        tmp_path / "user" / "config.toml",
        _MINIMAL_TOML + "\n[tiering]\ndaily_call_budget = 200\n",
    )
    enforced_path = _write(tmp_path / "enforced.toml", "[tiering]\ndaily_call_budget = 50\n")
    missing_default = tmp_path / "default" / "config.toml"

    config = load_config(
        user_config_path=user_path,
        system_default_config_paths=[missing_default],
        enforced_config_path=enforced_path,
    )

    assert config.tiering.daily_call_budget == 50


def test_load_config_raises_configloaderror_for_malformed_toml(tmp_path: Path) -> None:
    """Broken TOML syntax is a clear ConfigLoadError, not a raw
    tomllib.TOMLDecodeError."""
    user_path = _write(tmp_path / "user" / "config.toml", "this is not [ valid toml")
    missing_default = tmp_path / "default" / "config.toml"
    missing_enforced = tmp_path / "enforced.toml"

    with pytest.raises(ConfigLoadError):
        load_config(
            user_config_path=user_path,
            system_default_config_paths=[missing_default],
            enforced_config_path=missing_enforced,
        )


def test_load_config_raises_configloaderror_when_required_fields_are_missing(
    tmp_path: Path,
) -> None:
    """No tier ever sets `provider` — a clear ConfigLoadError, not a
    raw pydantic ValidationError leaking through unwrapped."""
    user_path = _write(tmp_path / "user" / "config.toml", "[tiering]\nalert_threshold = 0.6\n")
    missing_default = tmp_path / "default" / "config.toml"
    missing_enforced = tmp_path / "enforced.toml"

    with pytest.raises(ConfigLoadError):
        load_config(
            user_config_path=user_path,
            system_default_config_paths=[missing_default],
            enforced_config_path=missing_enforced,
        )


def test_load_config_resolves_socket_path_when_not_set_by_any_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """socket_path omitted from every tier: filled in via
    paths.resolve_socket_path() rather than staying None."""
    without_socket = _MINIMAL_TOML.replace(
        'socket_path = "/home/will/.local/state/spork/sporkd.sock"\n', ""
    )
    user_path = _write(tmp_path / "user" / "config.toml", without_socket)
    missing_default = tmp_path / "default" / "config.toml"
    missing_enforced = tmp_path / "enforced.toml"
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")

    config = load_config(
        user_config_path=user_path,
        system_default_config_paths=[missing_default],
        enforced_config_path=missing_enforced,
    )

    assert config.socket_path == Path("/run/user/1000/spork/sporkd.sock")
