"""Entities the structured knowledge base backend tracks (docs/DESIGN.md §10.8).

Plain frozen dataclasses, not pydantic — same choice `NormalizedMessage`
makes (`spork.core.models`): these are internal domain records, not a
schema validating arbitrary external input on their own (that's
`data.load_entity_data()`'s job, the same split
`spork.core.providers.file.messages.load_messages()` makes for
`NormalizedMessage`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Domain:
    """One tracked domain name and the company known to operate it.

    `company` is `None` when a domain is tracked with no owning
    company recorded — a domain's own entry and the company ->
    domain association are separate facts in source data (a company's
    `domains` list), so this is a normal state, not an error.
    """

    name: str
    company: str | None = None


@dataclass(frozen=True, slots=True)
class Company:
    """One tracked company: the domains it operates and the services
    it's known to provide.

    `domains`/`services` are the single source of truth for the
    domain -> company and service -> provider associations — `Domain.company`
    and `Service.provided_by` are both derived from these by a backend
    at load time, never stored redundantly in source data.
    """

    name: str
    domains: tuple[str, ...] = ()
    services: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Service:
    """One tracked service, and every company known to provide it.

    `provided_by` is computed by a backend from every `Company` that
    lists this service in its own `services` — more than one company
    can legitimately provide the same kind of service (e.g. both Gandi
    and Cloudflare offer DNS hosting).
    """

    name: str
    category: str | None = None
    provided_by: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Person:
    """One tracked person, optionally affiliated with a known company."""

    name: str
    email: str | None = None
    company: str | None = None
