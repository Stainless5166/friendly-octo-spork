"""Compose configured backends with runtime-only secret values."""

from collections.abc import Callable
from typing import Any

from spork.core.alerts.base import Alerter
from spork.core.alerts.loader import load_alerter
from spork.core.config.paths import resolve_secretspec_path
from spork.core.config.schema import BackendSpec, SporkConfig
from spork.core.context.base import ContextProvider
from spork.core.context.clients.null import NullContextProvider
from spork.core.context.loader import load_context_provider
from spork.core.llm.base import LLMClient
from spork.core.llm.loader import load_llm_client
from spork.core.llm.recording import RecordingLLMClient
from spork.core.providers.base import Provider
from spork.core.providers.loader import load_provider
from spork.core.receipts.extract import SenderDomainLookup
from spork.core.receipts.loader import load_receipt_extraction_client
from spork.core.receipts.pipeline import ReceiptArchiveComponents
from spork.core.secrets import Secrets, resolve_secrets

SecretResolver = Callable[..., Secrets]


def resolve_runtime_secrets(
    config: SporkConfig,
    *,
    reason: str,
    resolver: SecretResolver = resolve_secrets,
) -> Secrets:
    """Resolve SecretSpec once when any configured backend maps a secret."""
    specs: tuple[BackendSpec, ...] = (config.provider, config.llm, config.alerts)
    if config.context is not None:
        specs = (*specs, config.context)
    if config.receipt_archive is not None:
        specs = (*specs, config.receipt_archive.extraction)
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


def build_context_provider(config: SporkConfig, secrets: Secrets) -> ContextProvider:
    """Load the configured knowledgebase context provider, or the real
    "nothing configured" default when `[context]` is omitted."""
    if config.context is None:
        return NullContextProvider()
    return load_context_provider(
        config.context.spec,
        **materialize_backend_kwargs(config.context, secrets),
    )


def build_receipt_archive_components(
    config: SporkConfig,
    provider: Provider,
    context_provider: ContextProvider,
    secrets: Secrets,
) -> ReceiptArchiveComponents | None:
    """Compose the `archive_receipt` pipeline branch's collaborators
    (docs/DESIGN.md §9.5, M10), or `None` when `[receipt_archive]` is
    unconfigured — `build_default_pipeline()` already treats that as a
    real, valid "feature is off" state, not a caller-side special case.

    `attachment_fetcher`/`keyword_applier` come from the same `provider`
    every other capability does — `archive_receipt` is still one
    backend's entire relationship to spork, not a second provider
    concept. `domain_lookup` is the M9/M10 synergy: when the configured
    `context_provider` happens to structurally support `lookup_domain()`
    (checked via `isinstance` against the `@runtime_checkable`
    `SenderDomainLookup`, same pattern `CheckpointedProvider`/
    `BackfillProvider` already use for optional capabilities) it's
    passed straight through, so the deterministic extractor consults
    curated domain→company data ahead of its own learned cache — no
    separate seed-file mechanism. `NullContextProvider` (the default
    when `[context]` is unconfigured) never matches, so `domain_lookup`
    is `None` and the extractor relies on the learned cache alone.
    """
    if config.receipt_archive is None:
        return None
    extraction_client = load_receipt_extraction_client(
        config.receipt_archive.extraction.spec,
        **materialize_backend_kwargs(config.receipt_archive.extraction, secrets),
    )
    domain_lookup = context_provider if isinstance(context_provider, SenderDomainLookup) else None
    return ReceiptArchiveComponents(
        attachment_fetcher=provider.build_attachment_fetcher(),
        keyword_applier=provider.build_keyword_applier(),
        extraction_client=extraction_client,
        output_dir=config.receipt_archive.output_dir,
        domain_lookup=domain_lookup,
    )
