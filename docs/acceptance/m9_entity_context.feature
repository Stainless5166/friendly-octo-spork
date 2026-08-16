# Automated acceptance specification (not @manual): unlike the
# milestone-scoped specs elsewhere in this directory, this feature has
# no live Fastmail or LLM account dependency at all — EntityContextProvider
# is a self-contained, JSON-fixture-backed lookup subsystem
# (docs/DESIGN.md §10.8, docs/ROADMAP.md M9). Step bindings are not
# yet written (docs/acceptance/README.md's "bindings added milestone
# by milestone" convention) — the behavior described here is covered
# directly by the pytest suite in
# tests/core/context/clients/entities/, following this project's
# normal TDD convention, not by behave.
#
# This spec covers EntityContextProvider specifically, one of several
# knowledge base backends the ContextProvider seam is meant to hold
# (docs/DESIGN.md §10.8) — NullContextProvider and
# MarkdownVaultContextProvider are specified in prose there, not here.

@m9 @entity-context
Feature: Structured knowledge base context (domains, companies, services, people)
  Spork can look up known domains, companies, services, and people
  from a structured knowledge base backend, and turn a recognized
  sender into reference material a Tier 2 verdict can see —
  distinct from the free-text vault backend this same seam also holds.

  Background:
    Given an EntityContextProvider loaded from a fixture
    And the fixture defines the company "Gandi" with domain "gandi.com" providing the services "DNS hosting" and "Cloud hosting"

  Scenario: Looking up a known domain returns its operating company
    When the backend looks up domain "gandi.com"
    Then the domain record's company is "Gandi"

  Scenario: Looking up a known company returns its domains and services
    When the backend looks up company "Gandi"
    Then the company record's domains include "gandi.com"
    And the company record's services include "DNS hosting" and "Cloud hosting"

  Scenario: Looking up an unknown domain returns nothing
    When the backend looks up domain "unrecognized.example"
    Then no domain record is found

  Scenario: A service can be provided by more than one company
    Given the fixture also defines the company "Cloudflare" providing the service "DNS hosting"
    When the backend looks up service "DNS hosting"
    Then the service record's providers include "Gandi" and "Cloudflare"

  Scenario: A known person is linked to their affiliated company
    Given the fixture defines the person "Jane Doe" at "jane@gandi.com" affiliated with "Gandi"
    When the backend looks up person "jane@gandi.com"
    Then the person record's company is "Gandi"

  Scenario: Lookup keys are case-insensitive
    When the backend looks up domain "GANDI.COM"
    Then the domain record's company is "Gandi"

  @context-provider-seam
  Scenario: A message from a known sender gets real context; an unknown sender gets none
    Given a message from "jane@gandi.com"
    And a message from "someone@unrecognized.example"
    When the backend builds context for each message
    Then the message from the known domain has at least one context snippet
    And that snippet mentions "Gandi"
    And the message from the unrecognized domain has no context snippets
