"""Step bindings for the fixture-backed entity context provider (M9).

These scenarios exercise the real structured knowledge-base backend without
requiring a live account, network access, or an external fixture file.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from behave import given, then, when

from spork.core.context.clients.entities.provider import EntityContextProvider
from spork.core.models import NormalizedMessage


def _write_fixture(context: Any) -> None:
    """Persist the scenario's current entity data and reload its provider."""
    path: Path = context.entity_fixture_path
    path.write_text(json.dumps(context.entity_data))
    context.entity_provider = EntityContextProvider(path)


def _provider(context: Any) -> EntityContextProvider:
    """Return the provider stored by the scenario background."""
    provider: EntityContextProvider = context.entity_provider
    return provider


def _message(address: str) -> NormalizedMessage:
    """Build the smallest message shape needed by `get_context()`."""
    domain = address.rsplit("@", maxsplit=1)[-1]
    return NormalizedMessage(
        message_id=address,
        thread_id=address,
        from_address=address,
        from_domain=domain,
        subject="Acceptance message",
        body_text="Acceptance body",
    )


@given("an EntityContextProvider loaded from a fixture")
def entity_provider_loaded(context: Any) -> None:
    """Create an isolated, initially empty fixture for this scenario."""
    directory = Path(tempfile.mkdtemp(prefix="spork-m9-acceptance-"))
    context.entity_fixture_path = directory / "entities.json"
    context.entity_data = {"companies": [], "services": [], "people": []}
    _write_fixture(context)


@given(
    'the fixture defines the company "{company}" with domain "{domain}" '
    'providing the services "{first_service}" and "{second_service}"'
)
def fixture_defines_company(
    context: Any, company: str, domain: str, first_service: str, second_service: str
) -> None:
    """Add the primary company and its facts to the scenario fixture."""
    context.entity_data["companies"].append(
        {"name": company, "domains": [domain], "services": [first_service, second_service]}
    )
    _write_fixture(context)


@when('the backend looks up domain "{domain}"')
def lookup_domain(context: Any, domain: str) -> None:
    """Record the domain lookup result for its assertion step."""
    context.lookup_result = _provider(context).lookup_domain(domain)


@then('the domain record\'s company is "{company}"')
def domain_company_is(context: Any, company: str) -> None:
    """Verify that a domain resolves to the expected operating company."""
    assert context.lookup_result is not None
    assert context.lookup_result.company == company


@when('the backend looks up company "{company}"')
def lookup_company(context: Any, company: str) -> None:
    """Record the company lookup result for its assertion steps."""
    context.lookup_result = _provider(context).lookup_company(company)


@then('the company record\'s domains include "{domain}"')
def company_domains_include(context: Any, domain: str) -> None:
    """Verify that the company exposes the expected domain association."""
    assert context.lookup_result is not None
    assert domain in context.lookup_result.domains


@then('the company record\'s services include "{first_service}" and "{second_service}"')
def company_services_include(context: Any, first_service: str, second_service: str) -> None:
    """Verify that both services are present on the company record."""
    assert context.lookup_result is not None
    assert first_service in context.lookup_result.services
    assert second_service in context.lookup_result.services


@then("no domain record is found")
def no_domain_record(context: Any) -> None:
    """Verify that an unknown domain produces the normal empty lookup."""
    assert context.lookup_result is None


@given('the fixture also defines the company "{company}" providing the service "{service}"')
def fixture_defines_second_company(context: Any, company: str, service: str) -> None:
    """Add another service provider to test aggregation."""
    context.entity_data["companies"].append({"name": company, "services": [service]})
    _write_fixture(context)


@when('the backend looks up service "{service}"')
def lookup_service(context: Any, service: str) -> None:
    """Record the service lookup result for its assertion step."""
    context.lookup_result = _provider(context).lookup_service(service)


@then('the service record\'s providers include "{first_company}" and "{second_company}"')
def service_providers_include(context: Any, first_company: str, second_company: str) -> None:
    """Verify that every company offering the service is returned."""
    assert context.lookup_result is not None
    assert first_company in context.lookup_result.provided_by
    assert second_company in context.lookup_result.provided_by


@given('the fixture defines the person "{name}" at "{email}" affiliated with "{company}"')
def fixture_defines_person(context: Any, name: str, email: str, company: str) -> None:
    """Add a person and their company affiliation to the fixture."""
    context.entity_data["people"].append({"name": name, "email": email, "company": company})
    _write_fixture(context)


@when('the backend looks up person "{identifier}"')
def lookup_person(context: Any, identifier: str) -> None:
    """Record the person lookup result for its assertion step."""
    context.lookup_result = _provider(context).lookup_person(identifier)


@then('the person record\'s company is "{company}"')
def person_company_is(context: Any, company: str) -> None:
    """Verify that the person resolves to the expected company."""
    assert context.lookup_result is not None
    assert context.lookup_result.company == company


@given('a message from "{address}"')
def message_from(context: Any, address: str) -> None:
    """Collect a sender message for the context-provider seam scenario."""
    context.messages = getattr(context, "messages", [])
    context.messages.append(_message(address))


@when("the backend builds context for each message")
def build_context_for_messages(context: Any) -> None:
    """Build and retain context results in the same sender order."""
    context.context_results = [
        _provider(context).get_context(message) for message in context.messages
    ]


@then("the message from the known domain has at least one context snippet")
def known_message_has_context(context: Any) -> None:
    """Verify that the recognized sender received reference material."""
    assert context.context_results[0].snippets


@then('that snippet mentions "{text}"')
def snippet_mentions(context: Any, text: str) -> None:
    """Verify the known company's name appears in retrieved context."""
    assert any(text in snippet.text for snippet in context.context_results[0].snippets)


@then("the message from the unrecognized domain has no context snippets")
def unknown_message_has_no_context(context: Any) -> None:
    """Verify that an unknown sender produces an empty context result."""
    assert context.context_results[1].snippets == ()
