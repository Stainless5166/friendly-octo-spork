"""Acceptance tests for shared runtime backend composition (docs/DESIGN.md §6.4)."""

from __future__ import annotations

import json
from pathlib import Path

from spork.core.config.schema import (
    BackendSpec,
    LLMRecordingConfig,
    ReceiptArchiveConfig,
    SporkConfig,
)
from spork.core.context.base import ContextResult
from spork.core.context.clients.entities.provider import EntityContextProvider
from spork.core.context.clients.null import NullContextProvider
from spork.core.llm.base import LLMCallUsage, LLMResult, Verdict, VerdictRequest
from spork.core.providers.file.provider import FileProvider
from spork.core.receipts.llm import RecordedReceiptExtractionClient
from spork.core.runtime import (
    build_alerter,
    build_context_provider,
    build_llm_client,
    build_provider,
    build_receipt_archive_components,
    materialize_backend_kwargs,
    resolve_runtime_secrets,
)
from spork.core.secrets import Secrets


class _FixtureContextProvider:
    def __init__(self, label: str) -> None:
        self.label = label

    def get_context(self, message: object) -> ContextResult:
        return ContextResult(snippets=())


class _FixtureProvider:
    def __init__(self, label: str) -> None:
        self.label = label


class _FixtureLLMClient:
    def __init__(self, label: str) -> None:
        self.label = label

    def get_verdict(self, request: VerdictRequest) -> LLMResult:
        return LLMResult(
            verdict=Verdict.model_validate(
                {
                    "category": "fyi",
                    "urgency": "low",
                    "confidence": 0.9,
                    "suggested_action": {"type": "ignore"},
                    "summary": self.label,
                    "reasoning": "Fixture response.",
                }
            ),
            usage=LLMCallUsage(tokens_in=1, tokens_out=1),
        )


class _FixtureAlerter:
    def __init__(self, label: str) -> None:
        self.label = label

    def notify(
        self,
        title: str,
        body: str,
        *,
        url: str | None = None,
        urgency: str = "normal",
    ) -> None:
        pass


def _config(
    tmp_path: Path,
    *,
    secret_kwargs: bool = True,
    context: BackendSpec | None = None,
    receipt_archive: ReceiptArchiveConfig | None = None,
) -> SporkConfig:
    mapping = {"label": "BACKEND_LABEL"} if secret_kwargs else {}
    return SporkConfig(
        provider=BackendSpec(spec=f"{__name__}:_FixtureProvider", secret_kwargs=mapping),
        llm=BackendSpec(spec=f"{__name__}:_FixtureLLMClient", secret_kwargs=mapping),
        alerts=BackendSpec(spec=f"{__name__}:_FixtureAlerter", secret_kwargs=mapping),
        llm_recording=LLMRecordingConfig(corpus_path=tmp_path / "corpus" / "live.jsonl"),
        rules_path=tmp_path / "rules.toml",
        db_path=tmp_path / "state.sqlite3",
        context=context,
        receipt_archive=receipt_archive,
    )


def _request() -> VerdictRequest:
    return VerdictRequest(
        subject="Recorded subject",
        from_address="sender@example.com",
        to_addresses=(),
        cleaned_body="Body",
        thread_prior_subject=None,
        thread_user_has_replied=False,
        available_mailboxes=("Inbox",),
        available_categories=(),
        context_snippets=(),
    )


def test_materialize_backend_kwargs_injects_values_without_mutating_config() -> None:
    spec = BackendSpec(
        spec="example:Backend",
        kwargs={"host": "api.example.com"},
        secret_kwargs={"api_token": "JMAP_API_TOKEN"},
    )

    kwargs = materialize_backend_kwargs(spec, Secrets({"JMAP_API_TOKEN": "secret-value"}))

    assert kwargs == {"host": "api.example.com", "api_token": "secret-value"}
    assert spec.kwargs == {"host": "api.example.com"}


def test_runtime_resolves_secret_spec_once_for_all_configured_backends(tmp_path: Path) -> None:
    calls: list[tuple[Path, str]] = []

    def resolver(path: str | Path, *, reason: str) -> Secrets:
        calls.append((Path(path), reason))
        return Secrets({"BACKEND_LABEL": "resolved"})

    secrets = resolve_runtime_secrets(
        _config(tmp_path), reason="acceptance test", resolver=resolver
    )

    assert secrets.get("BACKEND_LABEL") == "resolved"
    assert len(calls) == 1
    assert calls[0][1] == "acceptance test"


def test_runtime_builders_inject_secrets_and_wrap_llm_recording(tmp_path: Path) -> None:
    config = _config(tmp_path)
    secrets = Secrets({"BACKEND_LABEL": "from-secret-spec"})

    provider = build_provider(config, secrets)
    llm_client = build_llm_client(config, secrets)
    alerter = build_alerter(config, secrets)
    result = llm_client.get_verdict(_request())

    assert provider.label == "from-secret-spec"  # type: ignore[attr-defined]
    assert alerter.label == "from-secret-spec"  # type: ignore[attr-defined]
    assert result.verdict.summary == "from-secret-spec"
    assert config.llm_recording is not None
    assert config.llm_recording.corpus_path.exists()


def test_build_context_provider_defaults_to_null_when_unconfigured(tmp_path: Path) -> None:
    """No [context] table: build_context_provider() returns the real
    "no knowledgebase configured" backend, not None/a crash."""
    config = _config(tmp_path)

    provider = build_context_provider(config, Secrets({}))

    assert isinstance(provider, NullContextProvider)


def test_resolve_runtime_secrets_includes_a_configured_context_providers_secret_kwargs(
    tmp_path: Path,
) -> None:
    """A [context] table's secret_kwargs count toward "does anything
    configured need SecretSpec resolved" the same way provider/llm/
    alerts already do — context isn't a silent fourth exception."""
    config = _config(
        tmp_path,
        secret_kwargs=False,
        context=BackendSpec(
            spec=f"{__name__}:_FixtureContextProvider", secret_kwargs={"label": "BACKEND_LABEL"}
        ),
    )
    calls: list[str] = []

    def resolver(path: str | Path, *, reason: str) -> Secrets:
        calls.append(reason)
        return Secrets({"BACKEND_LABEL": "resolved"})

    secrets = resolve_runtime_secrets(config, reason="acceptance test", resolver=resolver)

    assert secrets.get("BACKEND_LABEL") == "resolved"
    assert calls == ["acceptance test"]


def test_build_context_provider_loads_the_configured_backend(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        context=BackendSpec(
            spec=f"{__name__}:_FixtureContextProvider", kwargs={"label": "vault-label"}
        ),
    )

    provider = build_context_provider(config, Secrets({}))

    assert isinstance(provider, _FixtureContextProvider)
    assert provider.label == "vault-label"


def _file_provider(tmp_path: Path) -> FileProvider:
    messages_path = tmp_path / "messages.json"
    messages_path.write_text("[]")
    return FileProvider(messages_path, tmp_path / "actions.jsonl")


def _receipt_archive_config(
    tmp_path: Path, *, extraction_secret_kwargs: bool = False
) -> ReceiptArchiveConfig:
    responses_path = tmp_path / "extractions.json"
    responses_path.write_text("{}")
    return ReceiptArchiveConfig(
        output_dir=tmp_path / "receipts",
        extraction=BackendSpec(
            spec="spork.core.receipts.llm:RecordedReceiptExtractionClient",
            kwargs={"responses_path": str(responses_path)},
            secret_kwargs={"unused": "RECEIPT_SECRET"} if extraction_secret_kwargs else {},
        ),
    )


def test_build_receipt_archive_components_returns_none_when_unconfigured(tmp_path: Path) -> None:
    """No [receipt_archive] table: the feature is off entirely, not a
    crash and not an empty-but-present components bundle."""
    config = _config(tmp_path)

    components = build_receipt_archive_components(
        config, _file_provider(tmp_path), NullContextProvider(), Secrets({})
    )

    assert components is None


def test_build_receipt_archive_components_builds_real_collaborators(tmp_path: Path) -> None:
    config = _config(tmp_path, receipt_archive=_receipt_archive_config(tmp_path))
    provider = _file_provider(tmp_path)

    components = build_receipt_archive_components(
        config, provider, NullContextProvider(), Secrets({})
    )

    assert components is not None
    assert components.output_dir == config.receipt_archive.output_dir  # type: ignore[union-attr]
    assert isinstance(components.extraction_client, RecordedReceiptExtractionClient)
    # attachment_fetcher/keyword_applier come from the real provider,
    # not stand-ins -- prove they actually work.
    from spork.core.models import NormalizedMessage

    message = NormalizedMessage(
        message_id="msg-1",
        thread_id="thread-1",
        from_address="a@example.com",
        from_domain="example.com",
        subject="s",
        body_text="b",
    )
    assert components.attachment_fetcher.fetch_attachments(message) == ()
    components.keyword_applier.apply_keywords(message, ["receipt"])  # doesn't raise


def test_build_receipt_archive_components_leaves_domain_lookup_none_for_null_context(
    tmp_path: Path,
) -> None:
    """NullContextProvider doesn't support lookup_domain() -- the
    extractor falls back to StateDB's learned cache alone, same as
    when [context] is unconfigured entirely."""
    config = _config(tmp_path, receipt_archive=_receipt_archive_config(tmp_path))

    components = build_receipt_archive_components(
        config, _file_provider(tmp_path), NullContextProvider(), Secrets({})
    )

    assert components is not None
    assert components.domain_lookup is None


def test_build_receipt_archive_components_wires_an_entitycontextprovider_as_domain_lookup(
    tmp_path: Path,
) -> None:
    """The real M9/M10 synergy: a configured EntityContextProvider is
    passed straight through as domain_lookup, so the deterministic
    extractor consults its curated domain->company data ahead of
    StateDB's learned cache -- no separate seed-file mechanism."""
    entities_path = tmp_path / "entities.json"
    entities_path.write_text(
        json.dumps({"companies": [{"name": "Acme Cloud", "domains": ["acmecloud.com"]}]})
    )
    config = _config(tmp_path, receipt_archive=_receipt_archive_config(tmp_path))
    context_provider = EntityContextProvider(entities_path)

    components = build_receipt_archive_components(
        config, _file_provider(tmp_path), context_provider, Secrets({})
    )

    assert components is not None
    assert components.domain_lookup is context_provider
    resolved = components.domain_lookup.lookup_domain("acmecloud.com")  # type: ignore[union-attr]
    assert resolved is not None
    assert resolved.company == "Acme Cloud"


def test_resolve_runtime_secrets_includes_a_configured_receipt_archives_extraction_secret_kwargs(
    tmp_path: Path,
) -> None:
    """A [receipt_archive] table's extraction.secret_kwargs count
    toward "does anything configured need SecretSpec resolved" the
    same way provider/llm/alerts/context already do."""
    config = _config(
        tmp_path,
        secret_kwargs=False,
        receipt_archive=_receipt_archive_config(tmp_path, extraction_secret_kwargs=True),
    )
    calls: list[str] = []

    def resolver(path: str | Path, *, reason: str) -> Secrets:
        calls.append(reason)
        return Secrets({"RECEIPT_SECRET": "resolved"})

    secrets = resolve_runtime_secrets(config, reason="acceptance test", resolver=resolver)

    assert secrets.get("RECEIPT_SECRET") == "resolved"
    assert calls == ["acceptance test"]
