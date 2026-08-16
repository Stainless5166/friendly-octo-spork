# Manual/live acceptance specification for M3.

@manual @requires-fastmail @requires-anthropic @m3
Feature: Tier 2 LLM escalation
  Ambiguous mail receives a structured Claude verdict through LiteLLM,
  subject to validation, confidence policy, budget limits, and the
  never-send draft invariant.

  Background:
    Given a dedicated Fastmail test account is configured through SecretSpec
    And "ANTHROPIC_API_KEY" is available through SecretSpec
    And sporkd is configured with LiteLLM and a live model provider
    And the test account has Drafts and the configured triage mailboxes
    And a deterministic rule explicitly escalates the acceptance message

  @verdict
  Scenario: An escalated message receives a structured verdict
    When the acceptance message reaches Tier 2
    Then LiteLLM receives the documented prompt and forced deliver_verdict tool
    And the response contains a valid category, urgency, confidence, and action
    And the prompt hash, verdict, usage, and timestamp are recorded privately

  @confidence
  Scenario: A low-confidence verdict alerts without an irreversible action
    Given the model returns confidence below the alert threshold
    When Tier 2 validates the verdict
    Then the message is placed in the configured review mailbox
    And an alert is emitted
    And no irreversible action is applied automatically

  @budget
  Scenario: The daily LLM budget stops further calls
    Given the daily call budget has been exhausted
    When another message reaches Tier 2
    Then no model call is made
    And the message receives the configured budget-exhausted treatment
    And the daemon health alert is emitted at most once for the day

  @draft
  Scenario: A suggested reply creates a draft but never sends it
    Given the model returns a valid draft reply
    When Tier 2 applies the verdict
    Then a correctly threaded draft is created in Drafts
    And no EmailSubmission/set request is made
    And the human remains responsible for sending the draft

  @failure-safety
  Scenario: Invalid model output fails closed
    Given the model returns malformed or schema-invalid tool arguments
    When Tier 2 parses the response
    Then the response is rejected
    And no mailbox action or draft is created
    And the failure is recorded without marking the message successfully processed
