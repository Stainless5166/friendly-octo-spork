@acceptance-local @m2
Feature: Local deterministic Tier 1 acceptance
  A FileProvider fixture exercises deterministic rules, idempotency, and
  retry-safe action application without a mailbox connection.

  @first-match
  Scenario: The first matching local rule wins
    Given a local M2 FileProvider fixture with a message matching two rules
    When the local M2 message is processed by Tier 1
    Then the local M2 action log contains one move to "Reading"
    And the local M2 verdict identifies the specific rule
    And the local M2 message is marked processed

  @retry
  Scenario: A failed local action remains retryable
    Given a local M2 FileProvider fixture with a transiently failing action applier
    When the local M2 message is attempted and the action fails
    Then the local M2 message is not marked processed
    When the local M2 message is attempted again
    Then the local M2 action succeeds once
    And the local M2 message is marked processed
