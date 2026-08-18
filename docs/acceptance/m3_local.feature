@acceptance-local @m3
Feature: Local recorded Tier 2 acceptance
  Recorded verdicts and FileProvider logs exercise Tier 2 cost and safety
  behavior without a live model or mailbox.

  @confidence
  Scenario: A low-confidence recorded verdict alerts without acting
    Given a local M3 recorded response with confidence 0.2
    When the local M3 message is processed by Tier 2
    Then the local M3 message is marked processed
    And the local M3 action log is empty
    And the local M3 alert count is 1

  @budget
  Scenario: An exhausted local budget skips the model
    Given a local M3 recorded response and an exhausted daily budget
    When the local M3 message is processed by Tier 2
    Then the local M3 recorded client is not called
    And the local M3 message is marked processed
    And the local M3 alert urgency is "critical"

  @draft
  Scenario: A recorded reply creates a local draft and never sends
    Given a local M3 recorded response with draft text
    When the local M3 message is processed by Tier 2
    Then the local M3 drafts log contains the reply
    And the local M3 action log contains one tag

  @failure-safety
  Scenario: A verdict for an unavailable mailbox fails closed
    Given a local M3 recorded response targeting an unavailable mailbox
    When the local M3 message is processed by Tier 2 and validation fails
    Then the local M3 message is not marked processed
    And the local M3 action and drafts logs are empty
