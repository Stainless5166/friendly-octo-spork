"""`spork doctor` (docs/DESIGN.md §13/§14).

Unlike every other command in this codebase, `doctor` never stops at
the first failure: it runs each of its checks independently — secrets
 (§7.3), config, provider, LLM client, alerter, rules, the configured
local classifier if any (§9.1/§9.3), JMAP connectivity, and the
systemd unit's
install/enabled/active state (§14) — printing one `[ok]`/`[FAIL]` line
per check, and only exits non-zero once all of them have run and at
least one failed. "Tell me everything that's wrong" is the actual job
of a doctor command; a raw traceback is never an acceptable answer for
any of them.
"""

from __future__ import annotations

from dataclasses import dataclass

import typer

from spork.core.classify import registry as classify_registry
from spork.core.config.loader import load_config
from spork.core.config.paths import resolve_secretspec_path
from spork.core.config.schema import SporkConfig
from spork.core.providers.base import CheckpointedProvider
from spork.core.rules.loader import load_rules
from spork.core.runtime import build_alerter, build_llm_client, build_provider
from spork.core.secrets import Secrets, resolve_secrets
from spork.core.systemd.unit import check_unit_status


def _failure_detail(prefix: str, exc: Exception) -> str:
    """Turn library failures into one stable, single-line doctor detail."""
    message = next(
        (line.strip() for line in str(exc).splitlines() if line.strip()), "unknown error"
    )
    if prefix == "invalid configuration" and message.startswith("invalid config: "):
        message = message.removeprefix("invalid config: ")
    return f"{prefix}: {message}"


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """One check's outcome — a stable name, pass/fail, and a
    plain-language detail. Printed as one line regardless of what any
    other check found (see module docstring)."""

    name: str
    ok: bool
    detail: str


def doctor() -> None:
    """Run every check and report `[ok]`/`[FAIL]` for each; exit 1 if
    any of them failed."""
    checks = _run_checks()
    for check in checks:
        status = "ok" if check.ok else "FAIL"
        typer.echo(f"[{status}] {check.name}: {check.detail}")

    if any(not check.ok for check in checks):
        raise typer.Exit(code=1)


def _run_checks() -> list[DoctorCheck]:
    config_check, config = _check_config()
    secrets_check, secrets = _check_secrets()
    return [
        secrets_check,
        config_check,
        _check_provider(config, secrets),
        _check_llm(config, secrets),
        _check_alerter(config, secrets),
        _check_rules(config),
        _check_classifier(config),
        _check_jmap_connectivity(config, secrets),
        _check_systemd_unit(),
    ]


def _check_secrets() -> tuple[DoctorCheck, Secrets | None]:
    """The `secretspec check` equivalent (§7.3): every secret declared
    in the installed `secretspec.toml` actually resolves."""
    try:
        secrets = resolve_secrets(resolve_secretspec_path(), reason="spork doctor")
    except Exception as exc:
        return (
            DoctorCheck("secrets", False, _failure_detail("could not resolve secrets", exc)),
            None,
        )
    return DoctorCheck("secrets", True, "all declared secrets resolved"), secrets


def _check_config() -> tuple[DoctorCheck, SporkConfig | None]:
    """Also returns the loaded `SporkConfig` (or `None` on failure) so
    the provider/rules/classifier checks below don't each reload it."""
    try:
        config = load_config()
    except Exception as exc:
        return DoctorCheck("config", False, _failure_detail("invalid configuration", exc)), None
    return DoctorCheck("config", True, "loaded and validated"), config


def _check_provider(config: SporkConfig | None, secrets: Secrets | None) -> DoctorCheck:
    if config is None:
        return DoctorCheck("provider", False, "skipped — config failed to load")
    if secrets is None:
        return DoctorCheck("provider", False, "skipped — secrets failed to resolve")
    try:
        build_provider(config, secrets)
    except Exception as exc:
        return DoctorCheck("provider", False, _failure_detail("could not load provider", exc))
    return DoctorCheck("provider", True, f"loaded {config.provider.spec}")


def _check_llm(config: SporkConfig | None, secrets: Secrets | None) -> DoctorCheck:
    if config is None:
        return DoctorCheck("LLM client", False, "skipped — config failed to load")
    if secrets is None:
        return DoctorCheck("LLM client", False, "skipped — secrets failed to resolve")
    try:
        build_llm_client(config, secrets)
    except Exception as exc:
        return DoctorCheck("LLM client", False, _failure_detail("could not load LLM client", exc))
    return DoctorCheck("LLM client", True, f"loaded {config.llm.spec}")


def _check_alerter(config: SporkConfig | None, secrets: Secrets | None) -> DoctorCheck:
    if config is None:
        return DoctorCheck("alerter", False, "skipped — config failed to load")
    if secrets is None:
        return DoctorCheck("alerter", False, "skipped — secrets failed to resolve")
    try:
        build_alerter(config, secrets)
    except Exception as exc:
        return DoctorCheck("alerter", False, _failure_detail("could not load alerter", exc))
    return DoctorCheck("alerter", True, f"loaded {config.alerts.spec}")


def _check_rules(config: SporkConfig | None) -> DoctorCheck:
    if config is None:
        return DoctorCheck("rules", False, "skipped — config failed to load")
    try:
        rules = load_rules(config.rules_path)
    except Exception as exc:
        return DoctorCheck("rules", False, _failure_detail("could not load rules", exc))
    return DoctorCheck("rules", True, f"{len(rules)} rule(s) loaded from {config.rules_path}")


def _check_classifier(config: SporkConfig | None) -> DoctorCheck:
    if config is None:
        return DoctorCheck("local classifier", False, "skipped — config failed to load")
    name = config.tiering.local_classifier
    if name is None:
        return DoctorCheck("local classifier", True, "none configured")
    try:
        classify_registry.get(name)
    except Exception as exc:
        return DoctorCheck(
            "local classifier", False, _failure_detail("could not load local classifier", exc)
        )
    return DoctorCheck("local classifier", True, f"{name!r} registered")


def _check_jmap_connectivity(config: SporkConfig | None, secrets: Secrets | None) -> DoctorCheck:
    """Connect the configured checkpoint-capable provider, when applicable."""
    if config is None:
        return DoctorCheck("JMAP connectivity", False, "skipped — config failed to load")
    if secrets is None:
        return DoctorCheck("JMAP connectivity", False, "skipped — secrets failed to resolve")
    try:
        provider = build_provider(config, secrets)
        if not isinstance(provider, CheckpointedProvider):
            return DoctorCheck(
                "JMAP connectivity", True, "not applicable for the configured provider"
            )
        account_id = provider.account_id()
        if not account_id:
            return DoctorCheck("JMAP connectivity", False, "provider returned no account ID")
    except Exception as exc:
        return DoctorCheck(
            "JMAP connectivity", False, _failure_detail("could not connect to JMAP", exc)
        )
    return DoctorCheck("JMAP connectivity", True, f"connected to account {account_id}")


def _check_systemd_unit() -> DoctorCheck:
    """installed/enabled/active in one line (§14) — `spork
    install-service` is what changes the answer here."""
    try:
        status = check_unit_status()
    except Exception as exc:
        return DoctorCheck(
            "systemd unit", False, _failure_detail("could not check systemd unit", exc)
        )
    ok = status.installed and status.enabled == "enabled" and status.active == "active"
    detail = f"installed={status.installed} enabled={status.enabled} active={status.active}"
    return DoctorCheck("systemd unit", ok, detail)
