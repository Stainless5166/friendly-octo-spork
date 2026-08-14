"""`sporkd --help` prints usage and exits 0 (docs/ROADMAP.md M0).

Graduated from an xfail spec test now that spork.daemon.main uses
Typer (docs/DESIGN.md §6.3) to actually handle --help. Mirrors
tests/cli/test_main.py for the daemon entry point.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def test_help_prints_usage_and_exits_zero() -> None:
    """`sporkd --help` should exit 0 and print usage text, not crash."""
    result = subprocess.run(
        [sys.executable, "-m", "spork.daemon.main", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
    assert "Traceback" not in result.stderr


def test_version_prints_the_installed_version_and_exits_zero() -> None:
    """`sporkd --version` should exit 0 and print sporkd's own version,
    without falling through to the NotImplementedError daemon loop."""
    result = subprocess.run(
        [sys.executable, "-m", "spork.daemon.main", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "sporkd" in result.stdout.lower()


def test_no_usable_config_produces_a_clean_error_not_a_traceback(tmp_path: Path) -> None:
    """Running sporkd with no config.toml anywhere (none of the three
    tiers present) is a clear, reported ConfigLoadError — never a raw
    traceback, same convention as every other CLI command's genuinely
    unmet dependency (docs/ROADMAP.md M1's spork doctor/spork rules
    test)."""
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")  # empty, no spork/config.toml

    result = subprocess.run(
        [sys.executable, "-m", "spork.daemon.main"],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_log_level_option_appears_in_help() -> None:
    """docs/DESIGN.md §6.2 (M7): --log-level is real CLI surface, not
    just a config.toml field.

    TERM=dumb forces Typer/Click's Rich help renderer to plain text —
    with color enabled (as it is on GitHub Actions' runners), Rich
    inserts an ANSI escape sequence between "--" and "log-level" to
    style the dashes separately, splitting this exact substring apart
    even though the visible text is unchanged. Confirmed empirically
    (reproduced with FORCE_COLOR=1, fixed with TERM=dumb), not guessed
    — see tests/cli/test_main.py's identical fix for the CLI side.
    """
    env = dict(os.environ)
    env["TERM"] = "dumb"

    result = subprocess.run(
        [sys.executable, "-m", "spork.daemon.main", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )

    assert result.returncode == 0
    assert "--log-level" in result.stdout


def _write_minimal_config(config_dir: Path, tmp_path: Path) -> None:
    config_dir.mkdir(parents=True)
    messages_path = tmp_path / "messages.json"
    messages_path.write_text("[]")
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text("")
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
        responses_path = "{tmp_path / "responses.json"}"

        [alerts]
        spec = "spork.core.alerts.log:LoggingAlerter"
        """
    )
    (tmp_path / "responses.json").write_text("{}")


def test_an_invalid_log_level_produces_a_clean_error_not_a_traceback(tmp_path: Path) -> None:
    """A typo'd --log-level (bogus level name) is a clean CLI error —
    logging.Logger.setLevel()'s own ValueError, caught, not a raw
    traceback."""
    config_dir = tmp_path / "xdg-config-home" / "spork"
    _write_minimal_config(config_dir, tmp_path)
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg-config-home")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")

    result = subprocess.run(
        [sys.executable, "-m", "spork.daemon.main", "--log-level", "VERBOSE"],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_sporkd_starts_successfully_with_a_log_level_override(tmp_path: Path) -> None:
    """--log-level DEBUG doesn't break startup — a real running sporkd
    subprocess, same spawn-and-wait-for-the-socket pattern
    tests/cli/commands/test_status.py's own end-to-end test uses."""
    config_dir = tmp_path / "xdg-config-home" / "spork"
    _write_minimal_config(config_dir, tmp_path)
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg-config-home")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")
    socket_path = tmp_path / "sporkd.sock"

    daemon = subprocess.Popen(
        [sys.executable, "-m", "spork.daemon.main", "--log-level", "DEBUG"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not socket_path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert socket_path.exists(), "sporkd never created its control socket"
    finally:
        daemon.terminate()
        daemon.wait(timeout=5)


def test_an_unloadable_llm_spec_produces_a_clean_error_not_a_traceback(tmp_path: Path) -> None:
    """run_daemon() constructs an LLMClient at startup now that Tier 2
    is wired into the loop (docs/DESIGN.md §6.2.1) — a bad llm.spec
    must fail the same clean way every other load error does, not with
    a raw LLMClientLoadError traceback."""
    config_dir = tmp_path / "xdg-config-home" / "spork"
    config_dir.mkdir(parents=True)
    messages_path = tmp_path / "messages.json"
    messages_path.write_text("[]")
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text("")
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
        spec = "no.such.module:NoSuchClass"

        [alerts]
        spec = "spork.core.alerts.log:LoggingAlerter"
        """
    )
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg-config-home")
    env["XDG_CONFIG_DIRS"] = str(tmp_path / "xdg-config-dirs")

    result = subprocess.run(
        [sys.executable, "-m", "spork.daemon.main"],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert "Traceback" not in result.stderr
