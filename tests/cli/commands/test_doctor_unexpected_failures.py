"""Failure coverage for unexpected exceptions inside every doctor check."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import spork.cli.commands.doctor as doctor_module
from spork.core.secrets import Secrets


def _explode(*args: object, **kwargs: object) -> object:
    """Raise an untyped backend failure for doctor-boundary tests."""
    raise RuntimeError("backend exploded\nsecret-value-must-not-leak")


def _assert_single_line_failure(detail: str, prefix: str) -> None:
    assert detail.startswith(prefix)
    assert "\n" not in detail
    assert "secret-value-must-not-leak" not in detail


def test_secrets_check_catches_unexpected_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_module, "resolve_secrets", _explode)

    check, secrets = doctor_module._check_secrets()

    assert secrets is None
    assert not check.ok
    _assert_single_line_failure(check.detail, "could not resolve secrets:")


def test_config_check_catches_unexpected_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_module, "load_config", _explode)

    check, config = doctor_module._check_config()

    assert config is None
    assert not check.ok
    _assert_single_line_failure(check.detail, "invalid configuration:")


@pytest.mark.parametrize(
    ("check_name", "check_call", "prefix"),
    [
        (
            "provider",
            lambda: doctor_module._check_provider(object(), Secrets({})),
            "could not load provider:",
        ),
        (
            "LLM client",
            lambda: doctor_module._check_llm(object(), Secrets({})),
            "could not load LLM client:",
        ),
        (
            "alerter",
            lambda: doctor_module._check_alerter(object(), Secrets({})),
            "could not load alerter:",
        ),
    ],
)
def test_backend_checks_catch_unexpected_failure(
    monkeypatch: pytest.MonkeyPatch,
    check_name: str,
    check_call: object,
    prefix: str,
) -> None:
    builder_name = {
        "provider": "build_provider",
        "LLM client": "build_llm_client",
        "alerter": "build_alerter",
    }[check_name]
    monkeypatch.setattr(doctor_module, builder_name, _explode)

    check = check_call()  # type: ignore[operator]

    assert check.name == check_name
    assert not check.ok
    _assert_single_line_failure(check.detail, prefix)


def test_rules_check_catches_unexpected_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_module, "load_rules", _explode)

    check = doctor_module._check_rules(SimpleNamespace(rules_path=Path("rules.toml")))

    assert not check.ok
    _assert_single_line_failure(check.detail, "could not load rules:")


def test_classifier_check_catches_unexpected_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_module.classify_registry, "get", _explode)
    config = SimpleNamespace(tiering=SimpleNamespace(local_classifier="test"))

    check = doctor_module._check_classifier(config)

    assert not check.ok
    _assert_single_line_failure(check.detail, "could not load local classifier:")


def test_jmap_check_catches_unexpected_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_module, "build_provider", _explode)

    check = doctor_module._check_jmap_connectivity(object(), Secrets({}))

    assert not check.ok
    _assert_single_line_failure(check.detail, "could not connect to JMAP:")


def test_jmap_check_connects_checkpointed_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configured JMAP-shaped provider is actually connected by doctor."""

    class FakeCheckpointedProvider:
        def account_id(self) -> str:
            return "account-1"

        def build_checkpointed_source(self, cursor: str | None) -> object:
            return object()

    monkeypatch.setattr(
        doctor_module, "build_provider", lambda config, secrets: FakeCheckpointedProvider()
    )

    check = doctor_module._check_jmap_connectivity(object(), Secrets({}))

    assert check.ok
    assert check.detail == "connected to account account-1"


def test_jmap_check_rejects_an_empty_account_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider that cannot identify an account is not connected."""

    class EmptyAccountProvider:
        def account_id(self) -> str:
            return ""

        def build_checkpointed_source(self, cursor: str | None) -> object:
            return object()

    monkeypatch.setattr(
        doctor_module, "build_provider", lambda config, secrets: EmptyAccountProvider()
    )

    check = doctor_module._check_jmap_connectivity(object(), Secrets({}))

    assert not check.ok
    assert check.detail == "provider returned no account ID"


def test_systemd_check_catches_unexpected_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_module, "check_unit_status", _explode)

    check = doctor_module._check_systemd_unit()

    assert not check.ok
    _assert_single_line_failure(check.detail, "could not check systemd unit:")
