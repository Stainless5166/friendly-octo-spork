"""Acceptance tests for `spork doctor` (docs/DESIGN.md §13/§14).

Subprocess-based, matching tests/cli/commands/test_status.py's
pattern. `doctor` runs several independent checks and never stops at
the first failure — unlike every other command in this codebase, only
`doctor` needs "tell me everything that's wrong," which is what these
tests exercise: a from-scratch environment (nothing configured) fails
every check cleanly, a fully-configured one passes every check this
milestone can actually make pass (JMAP connectivity genuinely can't,
docs/ROADMAP.md M1 — same settled-shape-stub treatment as always).
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


def _bare_env(tmp_path: Path) -> dict[str, str]:
    """No config.toml, no secretspec.toml, nothing installed — every
    check should fail cleanly, none should crash."""
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg-config-home")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")  # empty, no real config
    env["HOME"] = str(tmp_path / "home")
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    return env


def _write_full_setup(tmp_path: Path) -> dict[str, str]:
    """A fully valid config.toml + secretspec.toml (env:// provider,
    so no real keyring is needed) under an isolated XDG_CONFIG_HOME —
    every check but JMAP connectivity and the systemd unit (neither
    installed here) should pass."""
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
    # SecretSpec's Python SDK resolves the *provider* from a separate,
    # genuinely global ~/.config/secretspec/config.toml (or
    # $XDG_CONFIG_HOME/secretspec/config.toml) — verified empirically:
    # the manifest's own [providers] table above is real and useful
    # (what the separate `secretspec` CLI tool reads) but the SDK's
    # resolve() ignores it without an explicit `provider=` argument, so
    # a from-scratch env needs this too, the same one-time
    # `secretspec config global init` a real user would run.
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


def test_doctor_help_works() -> None:
    """`spork doctor --help` exits 0 and prints usage, not a crash."""
    result = _run("doctor", "--help", env=dict(os.environ))

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_doctor_appears_in_top_level_help() -> None:
    """`spork --help` lists `doctor` as a command — confirms it's
    actually wired into the app, not just importable."""
    result = _run("--help", env=dict(os.environ))

    assert result.returncode == 0
    assert "doctor" in result.stdout.lower()


def test_doctor_fails_every_check_cleanly_against_a_bare_environment(tmp_path: Path) -> None:
    """Nothing configured at all: every check that depends on
    something existing fails, but doctor still exits cleanly — never a
    raw traceback."""
    result = _run("doctor", env=_bare_env(tmp_path))

    assert result.returncode == 1
    assert "[FAIL] secrets" in result.stdout
    assert "[FAIL] config" in result.stdout
    assert "[FAIL] JMAP connectivity" in result.stdout
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
    assert "Field required" not in result.stdout


def test_doctor_skips_provider_rules_and_classifier_checks_when_config_fails(
    tmp_path: Path,
) -> None:
    """provider/rules/local-classifier all need a loaded SporkConfig —
    reported as skipped, not silently omitted, not crashed on."""
    result = _run("doctor", env=_bare_env(tmp_path))

    assert "[FAIL] provider" in result.stdout
    assert "skipped" in result.stdout
    assert "[FAIL] rules" in result.stdout
    assert "[FAIL] local classifier" in result.stdout


def test_doctor_passes_every_check_a_full_setup_can_pass(tmp_path: Path) -> None:
    """secrets/config/provider/rules/local-classifier all pass against
    a fully valid setup — the file provider makes JMAP connectivity
    not applicable, while the systemd unit remains uninstalled in this
    sandbox and keeps the overall exit code non-zero."""
    result = _run("doctor", env=_write_full_setup(tmp_path))

    assert "[ok] secrets" in result.stdout
    assert "[ok] config" in result.stdout
    assert "[ok] provider" in result.stdout
    assert "[ok] rules" in result.stdout
    assert "[ok] local classifier" in result.stdout
    assert "[ok] JMAP connectivity: not applicable" in result.stdout
    assert result.returncode == 1


def test_doctor_reports_systemd_unit_state(tmp_path: Path) -> None:
    """The unit was never installed in this isolated $XDG_CONFIG_HOME —
    installed=False, regardless of whatever systemctl says beyond that."""
    result = _run("doctor", env=_write_full_setup(tmp_path))

    assert "systemd unit" in result.stdout


def test_doctor_warns_when_writes_lack_an_expected_account(tmp_path: Path) -> None:
    """Write-enabled beta config must carry an account identity fence."""
    env = _write_full_setup(tmp_path)
    config_path = tmp_path / "xdg-config-home" / "spork" / "config.toml"
    config_path.write_text(
        config_path.read_text().replace(
            "actions_log_path =", "allow_writes = true\n        actions_log_path ="
        )
    )

    result = _run("doctor", env=env)

    assert result.returncode == 1
    assert "[WARN] write safety: writes enabled without expected_account_email" in result.stdout
    assert "installed=False" in result.stdout
