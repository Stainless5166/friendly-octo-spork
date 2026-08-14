"""Compose configured backends with runtime-only secret values."""

from collections.abc import Callable
from typing import Any

from spork.core.alerts.base import Alerter
from spork.core.alerts.loader import load_alerter
from spork.core.config.paths import resolve_secretspec_path
from spork.core.config.schema import BackendSpec, SporkConfig
from spork.core.llm.base import LLMClient
from spork.core.llm.loader import load_llm_client
from spork.core.llm.recording import RecordingLLMClient
from spork.core.providers.base import Provider
from spork.core.providers.loader import load_provider
from spork.core.secrets import Secrets, resolve_secrets

SecretResolver = Callable[..., Secrets]


def resolve_runtime_secrets(
    config: SporkConfig,
    *,
    reason: str,
    resolver: SecretResolver = resolve_secrets,
) -> Secrets:
    """Resolve SecretSpec once when any configured backend maps a secret."""
    specs = (config.provider, config.llm, config.alerts)
    if not any(spec.secret_kwargs for spec in specs):
        return Secrets({})
    return resolver(resolve_secretspec_path(), reason=reason)


def materialize_backend_kwargs(spec: BackendSpec, secrets: Secrets) -> dict[str, Any]:
    """Build constructor kwargs without retaining resolved values in config."""
    kwargs = dict(spec.kwargs)
    kwargs.update(
        {argument: secrets.get(secret_name) for argument, secret_name in spec.secret_kwargs.items()}
    )
    return kwargs


def build_provider(config: SporkConfig, secrets: Secrets) -> Provider:
    """Load the configured provider with its mapped runtime secrets."""
    return load_provider(
        config.provider.spec,
        **materialize_backend_kwargs(config.provider, secrets),
    )


def build_llm_client(config: SporkConfig, secrets: Secrets) -> LLMClient:
    """Load the LLM client and apply corpus recording when enabled."""
    client = load_llm_client(
        config.llm.spec,
        **materialize_backend_kwargs(config.llm, secrets),
    )
    if config.llm_recording is not None:
        return RecordingLLMClient(client, corpus_path=config.llm_recording.corpus_path)
    return client


def build_alerter(config: SporkConfig, secrets: Secrets) -> Alerter:
    """Load the alerter with its mapped runtime secrets."""
    return load_alerter(
        config.alerts.spec,
        **materialize_backend_kwargs(config.alerts, secrets),
    )
