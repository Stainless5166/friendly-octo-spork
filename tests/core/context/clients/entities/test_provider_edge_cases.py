"""Edge-case tests for EntityContextProvider (docs/DESIGN.md §10.8,
docs/ROADMAP.md M9): not-found lookups, case-insensitivity, the
name-fallback for person lookups, category-only service metadata with
no provider yet, and the person snippet get_context() adds for a
recognized sender.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spork.core.context.clients.entities.provider import EntityContextProvider


def _write_fixture(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "entities.json"
    path.write_text(json.dumps(data))
    return path


def test_lookup_domain_returns_none_for_an_unknown_domain(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, {"companies": [{"name": "Gandi", "domains": ["gandi.com"]}]})
    provider = EntityContextProvider(data_path=path)

    assert provider.lookup_domain("unrecognized.example") is None


def test_lookup_company_returns_none_for_an_unknown_company(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, {"companies": [{"name": "Gandi"}]})
    provider = EntityContextProvider(data_path=path)

    assert provider.lookup_company("Cloudflare") is None


def test_lookup_service_returns_none_for_an_unknown_service(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, {"companies": [{"name": "Gandi", "services": ["DNS hosting"]}]})
    provider = EntityContextProvider(data_path=path)

    assert provider.lookup_service("Email hosting") is None


def test_lookup_person_returns_none_for_an_unknown_person(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path, {"companies": [{"name": "Gandi"}]})
    provider = EntityContextProvider(data_path=path)

    assert provider.lookup_person("nobody@example.com") is None


def test_lookups_are_case_insensitive_on_the_key(tmp_path: Path) -> None:
    """The key used to look something up is folded; the record returned
    keeps its original casing."""
    path = _write_fixture(
        tmp_path,
        {"companies": [{"name": "Gandi", "domains": ["gandi.com"], "services": ["DNS hosting"]}]},
    )
    provider = EntityContextProvider(data_path=path)

    domain = provider.lookup_domain("GANDI.COM")
    company = provider.lookup_company("gandi")
    service = provider.lookup_service("dns hosting")

    assert domain is not None and domain.name == "gandi.com"
    assert company is not None and company.name == "Gandi"
    assert service is not None and service.name == "DNS hosting"


def test_lookup_person_falls_back_to_name_when_no_email_matches(tmp_path: Path) -> None:
    path = _write_fixture(
        tmp_path,
        {"companies": [{"name": "Gandi"}], "people": [{"name": "Jane Doe", "company": "Gandi"}]},
    )
    provider = EntityContextProvider(data_path=path)

    person = provider.lookup_person("Jane Doe")

    assert person is not None
    assert person.company == "Gandi"


def test_lookup_service_includes_category_only_entries_with_no_provider_yet(
    tmp_path: Path,
) -> None:
    """The optional standalone "services" section can name a service no
    company has been recorded as providing yet — category metadata and
    provider list are independent facts."""
    path = _write_fixture(tmp_path, {"services": [{"name": "DNS hosting", "category": "infra"}]})
    provider = EntityContextProvider(data_path=path)

    service = provider.lookup_service("DNS hosting")

    assert service is not None
    assert service.category == "infra"
    assert service.provided_by == ()


def test_get_context_includes_a_person_snippet_when_the_sender_is_known(
    tmp_path: Path, make_message: Any
) -> None:
    path = _write_fixture(
        tmp_path,
        {
            "companies": [{"name": "Gandi", "domains": ["gandi.com"]}],
            "people": [{"name": "Jane Doe", "email": "jane@gandi.com", "company": "Gandi"}],
        },
    )
    provider = EntityContextProvider(data_path=path)

    result = provider.get_context(
        make_message(from_domain="gandi.com", from_address="jane@gandi.com")
    )

    assert len(result.snippets) == 2
    assert any("Jane Doe" in snippet.text for snippet in result.snippets)
