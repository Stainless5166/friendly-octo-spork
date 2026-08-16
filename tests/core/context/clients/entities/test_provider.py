"""Acceptance tests for EntityContextProvider (docs/DESIGN.md §10.8,
docs/ROADMAP.md M9) — a structured, JSON-fixture-backed
`ContextProvider` backend tracking domains, companies, services, and
people. One of several knowledge base backends this seam is meant to
hold, alongside `NullContextProvider`/`MarkdownVaultContextProvider`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spork.core.context.base import ContextResult
from spork.core.context.clients.entities.provider import EntityContextProvider


def _write_fixture(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "entities.json"
    path.write_text(json.dumps(data))
    return path


def test_lookup_domain_returns_the_operating_company(tmp_path: Path) -> None:
    path = _write_fixture(
        tmp_path,
        {"companies": [{"name": "Gandi", "domains": ["gandi.com"], "services": ["DNS hosting"]}]},
    )
    provider = EntityContextProvider(data_path=path)

    domain = provider.lookup_domain("gandi.com")

    assert domain is not None
    assert domain.company == "Gandi"


def test_lookup_company_returns_its_domains_and_services(tmp_path: Path) -> None:
    path = _write_fixture(
        tmp_path,
        {
            "companies": [
                {
                    "name": "Gandi",
                    "domains": ["gandi.com"],
                    "services": ["DNS hosting", "Cloud hosting"],
                }
            ]
        },
    )
    provider = EntityContextProvider(data_path=path)

    company = provider.lookup_company("Gandi")

    assert company is not None
    assert company.domains == ("gandi.com",)
    assert company.services == ("DNS hosting", "Cloud hosting")


def test_lookup_service_aggregates_providers_across_companies(tmp_path: Path) -> None:
    """A service several companies list independently comes back as one
    Service record naming every provider — not stored redundantly in
    the fixture, computed by the backend from each company's own
    `services` list."""
    path = _write_fixture(
        tmp_path,
        {
            "companies": [
                {"name": "Gandi", "services": ["DNS hosting"]},
                {"name": "Cloudflare", "services": ["DNS hosting"]},
            ]
        },
    )
    provider = EntityContextProvider(data_path=path)

    service = provider.lookup_service("DNS hosting")

    assert service is not None
    assert service.provided_by == ("Gandi", "Cloudflare")


def test_lookup_person_returns_their_affiliated_company(tmp_path: Path) -> None:
    path = _write_fixture(
        tmp_path,
        {
            "companies": [{"name": "Gandi"}],
            "people": [{"name": "Jane Doe", "email": "jane@gandi.com", "company": "Gandi"}],
        },
    )
    provider = EntityContextProvider(data_path=path)

    person = provider.lookup_person("jane@gandi.com")

    assert person is not None
    assert person.company == "Gandi"


def test_get_context_returns_a_snippet_for_a_known_sender_and_empty_for_unknown(
    tmp_path: Path, make_message: Any
) -> None:
    """The whole point of this backend: a Tier 2 verdict sees different
    context for a recognized sender than an unrecognized one."""
    path = _write_fixture(
        tmp_path,
        {"companies": [{"name": "Gandi", "domains": ["gandi.com"], "services": ["DNS hosting"]}]},
    )
    provider = EntityContextProvider(data_path=path)

    known = provider.get_context(make_message(from_domain="gandi.com"))
    unknown = provider.get_context(make_message(from_domain="unrecognized.example"))

    assert known.snippets != ()
    assert any("Gandi" in snippet.text for snippet in known.snippets)
    assert unknown == ContextResult(snippets=())
