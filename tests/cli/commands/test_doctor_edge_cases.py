"""Failure/edge-case tests for `spork doctor` (docs/DESIGN.md §13/§14).

Companion to test_doctor.py's acceptance tests — covers the
provider/rules/local-classifier checks' own failure branches
(ProviderLoadError/RulesLoadError/UnknownClassifierError), reachable
only with a config that itself loads successfully but names something
bad underneath it.
"""

from __future__ import annotations

import os
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


def _write_full_setup(tmp_path: Path) -> dict[str, str]:
    """Same fully-valid setup as test_doctor.py's own helper — a
    config.toml + secretspec.toml (env:// provider, plus the separate
    *global* ~/.config/secretspec/config.toml SecretSpec's SDK
    actually reads the provider from) under an isolated
    XDG_CONFIG_HOME. Duplicated rather than imported — this codebase's
    convention for CLI test helpers (see test_reclassify_edge_cases.py)."""
    xdg_config_home = tmp_path / "xdg-config-home"
    config_dir = xdg_config_home / "spork"
    config_dir.mkdir(parents=True)

    messages_path = tmp_path / "messages.json"
    messages_path.write_text("[]")
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
        [[rule]]
        id = "catch-all"
        when = { always = true }
        action = { type = "tag", mailbox = "Inbox" }
        """
    )
    responses_path = tmp_path / "responses.json"
    responses_path.write_text("{}")

    (config_dir / "config.toml").write_text(
        f"""
        rules_path = "{rules_path}"
        db_path = "{tmp_path / "state.sqlite3"}"
        socket_path = "{tmp_path / "sporkd.sock"}"

        [provider]
        spec = "spork.core.providers.file.provider:FileProvider"
        [provider.kwargs]
        messages_path = "{messages_path}"
        actions_log_path = "{tmp_path / "actions.jsonl"}"

        [llm]
        spec = "spork.core.llm.clients.recorded:RecordedLLMClient"
        [llm.kwargs]
        responses_path = "{responses_path}"

        [alerts]
        spec = "spork.core.alerts.log:LoggingAlerter"
        """
    )
    (config_dir / "secretspec.toml").write_text(
        """
        [project]
        name = "spork-test"
        revision = "1.0"

        [profiles.default]
        JMAP_API_TOKEN = { description = "test" }
        ANTHROPIC_API_KEY = { description = "test" }

        [providers]
        default = "env://"
        """
    )
    secretspec_global_dir = xdg_config_home / "secretspec"
    secretspec_global_dir.mkdir(parents=True)
    (secretspec_global_dir / "config.toml").write_text(
        """
        [defaults]
        provider = "env://"
        """
    )

    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(xdg_config_home)
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")
    env["HOME"] = str(tmp_path / "home")
    env["JMAP_API_TOKEN"] = "test-jmap-token"
    env["ANTHROPIC_API_KEY"] = "test-anthropic-key"
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    return env


def _reload_config_with(tmp_path: Path, **overrides: str) -> dict[str, str]:
    """Reuses _write_full_setup()'s fully-valid environment, then
    rewrites config.toml with one field swapped for something bad —
    everything else (secretspec, other config fields) stays valid, so
    only the check under test should fail."""
    env = _write_full_setup(tmp_path)
    config_path = Path(env["XDG_CONFIG_HOME"]) / "spork" / "config.toml"
    text = config_path.read_text()
    for key, value in overrides.items():
        text = text.replace(key, value)
    config_path.write_text(text)
    return env


def test_doctor_reports_provider_failure_when_the_spec_is_bad(tmp_path: Path) -> None:
    env = _reload_config_with(
        tmp_path,
        **{
            'spec = "spork.core.providers.file.provider:FileProvider"': (
                'spec = "nonexistent.module:NoSuchProvider"'
            )
        },
    )

    result = _run("doctor", env=env)

    assert "[FAIL] provider" in result.stdout
    assert "[ok] config" in result.stdout


def test_doctor_reports_rules_failure_when_the_rules_file_is_missing(tmp_path: Path) -> None:
    env = _write_full_setup(tmp_path)
    config_path = Path(env["XDG_CONFIG_HOME"]) / "spork" / "config.toml"
    # Point rules_path at something that was never written.
    text = config_path.read_text().replace(
        str(tmp_path / "rules.toml"), str(tmp_path / "does-not-exist.toml")
    )
    config_path.write_text(text)

    result = _run("doctor", env=env)

    assert "[FAIL] rules" in result.stdout
    assert "[ok] config" in result.stdout


def test_doctor_reports_local_classifier_failure_when_unregistered(tmp_path: Path) -> None:
    """No classifier backend is registered by default anywhere in this
    codebase yet (docs/DESIGN.md §9.1's classify/keyword.py is still
    planned) — naming any local_classifier in a fresh process is
    always an UnknownClassifierError, which is exactly what this
    checks."""
    env = _write_full_setup(tmp_path)
    config_path = Path(env["XDG_CONFIG_HOME"]) / "spork" / "config.toml"
    with config_path.open("a") as f:
        f.write('\n[tiering]\nlocal_classifier = "does-not-exist"\n')

    result = _run("doctor", env=env)

    assert "[FAIL] local classifier" in result.stdout
    assert "[ok] config" in result.stdout


def test_doctor_reports_local_classifier_ok_when_none_configured(tmp_path: Path) -> None:
    """The default: no local_classifier at all is a valid, complete
    configuration, not a failure."""
    result = _run("doctor", env=_write_full_setup(tmp_path))

    assert "[ok] local classifier: none configured" in result.stdout
