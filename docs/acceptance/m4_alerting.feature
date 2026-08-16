# Manual/live acceptance specification for M4.

@manual @requires-fastmail @m4
Feature: Human alerting
  Spork alerts the operator for urgent, uncertain, and daemon-health
  conditions without making alert delivery a hidden failure point.

  Background:
    Given a dedicated Fastmail test account is configured through SecretSpec
    And sporkd is running with alert logging enabled
    And the test account has a safe acceptance mailbox for review items

  @vip
  Scenario: A VIP rule emits an immediate alert
    Given a new message matches a VIP rule with alert_immediately enabled
    When Tier 1 processes the message
    Then the configured alerter emits one alert with the expected urgency
    And the action and alert share the message correlation ID

  @tier2
  Scenario: Confidence bands produce the documented alert behavior
    Given test messages produce low, middle, and high confidence verdicts
    When Tier 2 processes the messages
    Then low confidence produces a review action and an alert
    And middle confidence produces the configured action and an alert
    And high confidence produces the configured action without an alert unless urgency is high

  @push-health
  Scenario: A prolonged push outage emits one health alert
    Given sporkd reports a JMAP push disconnect
    When the disconnect lasts longer than the configured threshold
    Then one critical push-disconnected alert is emitted
    And polling continues during the outage
    When push recovers
    Then the outage state is cleared
    And a second alert is not emitted for the same outage

  @dbus
  Scenario: Missing DBus degrades to logging
    Given no DBus session bus is available
    When an alert is generated
    Then sporkd continues running
    And the alert is recorded in the operational log
    And the missing desktop delivery does not lose the triage decision
