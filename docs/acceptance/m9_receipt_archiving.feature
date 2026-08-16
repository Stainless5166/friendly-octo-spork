# Offline acceptance specification for M9 (planned — see docs/ROADMAP.md).
#
# Unlike m2/m3/m4's @manual specs, nothing here needs a live Fastmail or
# Anthropic account: every scenario runs against FileProvider and a
# recorded receipt-extraction fixture, the same "no live network in the
# test run itself" shape as m1_jmap_fault_injection.feature. That's the
# point of the design (docs/DESIGN.md §9.5) — deterministic-first,
# LLM escalation narrow and recorded, so the whole pipeline is honestly
# testable without a live account.
#
# Currently @wip: the underlying spork.core.receipts.* modules don't
# exist yet (docs/ROADMAP.md M9), so every step below raises
# NotImplementedError. @wip scenarios are skipped by the safe default
# `uv run behave` (docs/acceptance/environment.py), same mechanism as
# @manual but for "not built yet" instead of "needs a live account".
# Run `SPORK_ACCEPTANCE_WIP=1 uv run behave --tags=m9` to see the
# current gap directly. Drop @wip only once real step bindings replace
# these stubs and the scenarios pass for real.

@m9 @receipt-archiving @wip
Feature: Automatic-payment receipt tagging and archiving
  Spork recognizes automatic-payment receipt emails, tags them with
  receipt/company/date, and archives a single combined PDF (the message
  plus every attachment) to a configured location — deterministically
  wherever a sender is already known, escalating to one narrow Tier 2
  extraction call only the first time a sender is seen, and remembering
  that sender afterward.

  Background:
    Given a rules file with a rule that recognizes automatic-payment receipts
    And a receipt archive output directory is configured
    And the known-senders registry is seeded with "billing.acmecloud.com" as "Acme Cloud"

  @deterministic @no-llm
  Scenario: A known sender is tagged and archived without any Tier 2 call
    Given a receipt email from "billing.acmecloud.com" with one PDF invoice attachment
    When the message is processed by Tier 1
    Then the message is tagged "receipt", "company:Acme Cloud", and a "date:" tag matching the invoice date
    And a single combined PDF containing the message and its attachment is saved to the configured output directory
    And no Tier 2 call is made

  @llm-escalation @learning
  Scenario: An unrecognized sender is extracted via Tier 2 and then learned
    Given a receipt email from the unrecognized domain "billing.newvendor.io"
    When the message is processed by Tier 1
    Then exactly one Tier 2 receipt-extraction call is made
    And the message is tagged "receipt", "company:New Vendor Inc", and a "date:" tag matching the extracted date
    And a single combined PDF is saved to the configured output directory
    And "billing.newvendor.io" is recorded in the known-senders registry as "New Vendor Inc"

  @learning
  Scenario: A previously-learned sender is handled deterministically on the next message
    Given "billing.newvendor.io" was learned as "New Vendor Inc" by an earlier Tier 2 call
    When a second receipt email from "billing.newvendor.io" is processed by Tier 1
    Then the message is tagged and archived without any Tier 2 call

  @pdf-generation
  Scenario: A receipt with no attachments is still archived from its own content
    Given a receipt email from "billing.acmecloud.com" with no attachments
    When the message is processed by Tier 1
    Then a single PDF built from the message content alone is saved to the configured output directory

  @pdf-generation
  Scenario: Multiple attachments and the message body combine into exactly one PDF
    Given a receipt email from "billing.acmecloud.com" with a PDF attachment and an image attachment
    When the message is processed by Tier 1
    Then exactly one PDF file is saved to the configured output directory
    And that PDF contains the message content followed by both attachments in order

  @non-receipt
  Scenario: An ordinary message is left to its normal rule, not archived
    Given a message that does not match the receipt rule
    When the message is processed by Tier 1
    Then no PDF is archived
    And the message is handled by its normal matching rule instead

  @audit @failure-safety
  Scenario: An unwritable archive location fails safely and stays retryable
    Given the configured output directory cannot be written to
    When a known-sender receipt email is processed by Tier 1
    Then the failure is reported without a raw traceback
    And the message is not marked processed
    And the next acquisition cycle can retry the message
