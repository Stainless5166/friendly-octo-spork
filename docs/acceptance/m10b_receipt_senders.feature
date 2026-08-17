# Offline acceptance specification for the known-sender registry +
# deterministic extractor (docs/ROADMAP.md M10, docs/DESIGN.md §9.5).
# Reusable independent of the rest of the receipt-archiving pipeline:
# this module only knows about a message, a StateDB-backed learned
# cache, and an optional curated domain lookup. No live account, no
# network, no LLM call anywhere in this feature.

@m10 @receipt-senders
Feature: Known-sender registry and deterministic company/date extraction
  A sender domain spork has already learned resolves company and date
  without any Tier 2 call; an unrecognized sender declines rather than
  guessing.

  @learned
  Scenario: A previously-learned sender is extracted deterministically
    Given "billing.acmecloud.com" was learned as "Acme Cloud" in the registry
    When a receipt message from "billing.acmecloud.com" with a Date header is extracted
    Then the extraction succeeds with company "Acme Cloud"

  @curated
  Scenario: A curated domain lookup takes priority over a learned entry
    Given "billing.acmecloud.com" was learned as "Wrong Name" in the registry
    And a curated domain lookup resolves "billing.acmecloud.com" to "Acme Cloud"
    When a receipt message from "billing.acmecloud.com" with a Date header is extracted
    Then the extraction succeeds with company "Acme Cloud"

  @unrecognized
  Scenario: An unrecognized sender declines rather than guessing
    When a receipt message from "billing.unrecognized.example" with a Date header is extracted
    Then the extraction declines

  @no-date
  Scenario: A resolvable company with no date anywhere declines
    Given "billing.acmecloud.com" was learned as "Acme Cloud" in the registry
    When a receipt message from "billing.acmecloud.com" with no date anywhere is extracted
    Then the extraction declines

  @learning
  Scenario: Learning a sender makes the next message from it extractable
    When a receipt message from "billing.newvendor.io" with a Date header is extracted
    Then the extraction declines
    When "billing.newvendor.io" is learned as "New Vendor Inc" in the registry
    And a second receipt message from "billing.newvendor.io" with a Date header is extracted
    Then the extraction succeeds with company "New Vendor Inc"
