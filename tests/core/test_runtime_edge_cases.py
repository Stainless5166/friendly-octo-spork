"""Failure and opt-out coverage for shared runtime composition."""

from pathlib import Path

import pytest

from spork.core.config.schema import BackendSpec, SporkConfig
from spork.core.runtime import build_llm_client, materialize_backend_kwargs, resolve_runtime_secrets
from spork.core.secrets import Secrets, SecretsError


class _FixtureLLMClient:
    def __init__(self, label: str = "plain") -> None:
        self.label = label


def _config(tmp_path: Path) -> SporkConfig:
    return SporkConfig(
        provider=BackendSpec(spec="example:Provider"),
        llm=BackendSpec(spec=f"{__name__}:_FixtureLLMClient"),
        alerts=BackendSpec(spec="example:Alerter"),
        rules_path=tmp_path / "rules.toml",
        db_path=tmp_path / "state.sqlite3",
    )


def test_runtime_skips_secretspec_when_no_backend_maps_a_secret(tmp_path: Path) -> None:
    def unexpected_resolver(path: str | Path, *, reason: str) -> Secrets:
        pytest.fail(f"resolver called for {path} because {reason}")

    secrets = resolve_runtime_secrets(
        _config(tmp_path), reason="no mappings", resolver=unexpected_resolver
    )

    assert repr(secrets) == "Secrets(names=[])"


def test_materialization_reports_an_unresolved_mapped_name_cleanly() -> None:
    spec = BackendSpec(
        spec="example:Backend",
        secret_kwargs={"api_token": "MISSING_TOKEN"},
    )

    with pytest.raises(SecretsError, match="MISSING_TOKEN"):
        materialize_backend_kwargs(spec, Secrets({}))


def test_llm_builder_does_not_record_when_recording_is_unconfigured(tmp_path: Path) -> None:
    client = build_llm_client(_config(tmp_path), Secrets({}))

    assert isinstance(client, _FixtureLLMClient)
    assert client.label == "plain"
