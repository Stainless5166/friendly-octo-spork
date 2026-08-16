"""EntityContextProvider: a structured, file-backed knowledge base
ContextProvider backend (docs/DESIGN.md §10.8, docs/ROADMAP.md M9).

Exists to prove the `ContextProvider` seam generalizes beyond
free-text retrieval (`NullContextProvider`/`MarkdownVaultContextProvider`)
with a second real implementation: structured facts about domains,
companies, services, and people (e.g. "gandi.com is operated by
Gandi, which provides DNS hosting and Cloud hosting"). Reads a
literal, explicitly supplied JSON fixture once at construction and
answers every lookup from in-memory indices built at that time — no
re-read per lookup, matching `_FileMessageLookup`'s "load once at
construction" precedent, except this backend keeps indices instead of
scanning a list per call since lookups are meant to run hot inside a
Tier 2 decision path.

Lookups are case-insensitive on the key (domain name, company name,
service name, person email/name) — a domain header or a name typed in
prose can be cased differently than how it was entered in the
fixture — but the stored record's own casing (what a lookup
*returns*) is always preserved as authored, only the *key* used to
find it is folded.
"""

from __future__ import annotations

from pathlib import Path

from spork.core.context.base import ContextResult, ContextSnippet
from spork.core.context.clients.entities.data import load_entity_data
from spork.core.context.clients.entities.models import Company, Domain, Person, Service
from spork.core.models import NormalizedMessage


def _render_company(company: Company) -> str:
    """Render one company's known facts as a single prose sentence —
    the whole point of "reference material, never instructions" (§10.8):
    plain text a model reads, not structured data it could mistake for
    an instruction."""
    text = company.name
    if company.domains:
        text += f" operates {', '.join(company.domains)}"
    if company.services:
        text += f" and provides {', '.join(company.services)}"
    return text + "."


def _render_person(person: Person) -> str:
    return f"{person.name} is affiliated with {person.company}."


class EntityContextProvider:
    """Structurally satisfies `ContextProvider` (docs/DESIGN.md §10.8)."""

    def __init__(self, data_path: str | Path) -> None:
        data = load_entity_data(data_path)

        self._companies: dict[str, Company] = {
            company.name.lower(): company for company in data.companies
        }

        self._domains: dict[str, Domain] = {}
        for company in data.companies:
            for domain_name in company.domains:
                self._domains[domain_name.lower()] = Domain(name=domain_name, company=company.name)

        # Service.provided_by is derived, not stored — every company
        # that lists a given service name contributes one entry, in
        # fixture order, and the first company encountered to mention
        # it also fixes the display casing.
        display_name_by_key: dict[str, str] = {}
        providers_by_key: dict[str, list[str]] = {}
        for company in data.companies:
            for service_name in company.services:
                key = service_name.lower()
                display_name_by_key.setdefault(key, service_name)
                providers_by_key.setdefault(key, []).append(company.name)

        category_by_key = {meta.name.lower(): meta.category for meta in data.service_metadata}
        for meta in data.service_metadata:
            display_name_by_key.setdefault(meta.name.lower(), meta.name)

        self._services: dict[str, Service] = {
            key: Service(
                name=display_name_by_key[key],
                category=category_by_key.get(key),
                provided_by=tuple(providers_by_key.get(key, ())),
            )
            for key in display_name_by_key
        }

        self._people_by_email: dict[str, Person] = {
            person.email.lower(): person for person in data.people if person.email
        }
        self._people_by_name: dict[str, Person] = {
            person.name.lower(): person for person in data.people
        }

    def lookup_domain(self, domain: str) -> Domain | None:
        return self._domains.get(domain.lower())

    def lookup_company(self, name: str) -> Company | None:
        return self._companies.get(name.lower())

    def lookup_service(self, name: str) -> Service | None:
        return self._services.get(name.lower())

    def lookup_person(self, identifier: str) -> Person | None:
        """Look up by email first, falling back to name — most callers
        (`get_context()`) have a `from_address` on hand, but a name is
        also a reasonable identifier for direct lookups."""
        key = identifier.lower()
        return self._people_by_email.get(key) or self._people_by_name.get(key)

    def get_context(self, message: NormalizedMessage) -> ContextResult:
        """Turn a recognized `from_domain`/`from_address` into
        `ContextSnippet`s; an unrecognized sender — the overwhelmingly
        common case for a hand-curated fixture — returns an empty
        result, not an error, same contract every lookup above uses."""
        domain = self.lookup_domain(message.from_domain)
        if domain is None or domain.company is None:
            return ContextResult(snippets=())

        company = self.lookup_company(domain.company)
        if company is None:
            return ContextResult(snippets=())

        snippets = [ContextSnippet(source=domain.name, text=_render_company(company))]

        person = self.lookup_person(message.from_address)
        if person is not None and person.company is not None:
            snippets.append(
                ContextSnippet(source=message.from_address, text=_render_person(person))
            )

        return ContextResult(snippets=tuple(snippets))
