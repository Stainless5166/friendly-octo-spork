@manual @requires-fastmail @m8
Feature: Company-mail safety gate
  Spork must prove its read-only and observer boundaries before it is
  allowed to run against a company mailbox.

  @observer
  Scenario: Observer mode cannot invoke Tier 2 or mutate production state
    Given a dedicated company-mail test account is configured
    And sporkd is started with the observer profile
    When the observer processes a bounded batch of messages
    Then no LLM client is constructed or called
    And no mailbox mutation or draft creation is attempted
    And no production state database, cursor, or audit record is written
    And the observer exits with aggregate-only results

  @report
  Scenario: A read-only report proves the current escalation surface
    Given a dedicated company-mail test account is configured
    When the operator runs "spork report --limit 50 --actions-out planned-actions.jsonl"
    Then the command performs no mailbox mutation
    And the output contains aggregate counts only
    And the action plan contains one sanitized record per sampled message
    And the report identifies messages that would escalate without exposing message content

  @gate
  Scenario: Production is blocked until the safety evidence is approved
    Given the observer and read-only report evidence is available
    When the maintainer reviews the company-mail safety gate
    Then Tier 2 remains disabled until explicit approval
    And unattended company-mail operation is not declared complete
