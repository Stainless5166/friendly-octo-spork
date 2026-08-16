# Manual/live acceptance specification for M2.

@manual @requires-fastmail @m2
Feature: Deterministic Tier 1 rules
  Spork applies deterministic rules before any LLM call and records a
  repeatable, auditable outcome.

  Background:
    Given a dedicated Fastmail test account is configured through SecretSpec
    And sporkd is running with JmapProvider
    And the configured LLM client is unavailable or instrumented to fail if called
    And a rules file contains sender, domain, and catch-all rules

  @first-match
  Scenario: The first matching rule determines the action
    Given a message matches both a specific sender rule and a later catch-all rule
    When the message is processed by Tier 1
    Then only the first enabled matching rule determines the action
    And no Tier 2 call is made
    And the action is recorded in the audit log

  @actions
  Scenario: A deterministic action is applied exactly once
    Given a new message matches a move rule
    When sporkd processes the message
    Then the configured mailbox action is applied
    And the message is marked processed
    When the same JMAP change is observed again after a restart
    Then the action is not applied a second time

  @dry-run
  Scenario: Rules test has no side effects
    Given a validated rules file and recent messages in the test Inbox
    When the operator runs "spork rules test" for that rules file
    Then matching decisions are displayed
    And no mailbox mutation is sent
    And no message is marked processed
    And no LLM call is made

  @audit
  Scenario: A failed action remains retryable
    Given a message matches a rule whose action endpoint returns a transient failure
    When Tier 1 attempts the action
    Then the failure is reported without a raw traceback
    And the message is not marked processed
    And the next acquisition cycle can retry the message
