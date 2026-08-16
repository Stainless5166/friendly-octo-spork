# Manual/live acceptance specification for M7.

@manual @requires-fastmail @requires-anthropic @requires-systemd-user @m7
Feature: Unattended production readiness
  Spork can run unattended for a full week with decisions and control
  changes reconstructable from logs and the audit trail.

  Background:
    Given a dedicated Fastmail test or approved daily-driver account is configured
    And the Anthropic provider is configured through SecretSpec
    And systemd runs sporkd at user login
    And operational logs and the state database are retained for the test period

  @calibration
  Scenario: Confidence thresholds are tuned against real triage decisions
    Given a representative sample of real ambiguous messages has been reviewed by a human
    When verdict confidence is compared with the human decisions
    Then threshold changes are recorded with their rationale
    And no threshold is changed from fabricated fixture outcomes alone

  @rate-limit
  Scenario: Rate limits do not cause silent loss or unsafe retries
    When the provider returns a documented rate-limit response
    Then the daemon logs the rate-limit event
    And it applies bounded retry or fallback behavior
    And it does not duplicate an irreversible action
    And the affected message remains replayable

  @week
  Scenario: The daemon runs unattended for one week
    When the daemon processes the account for seven consecutive days
    Then it requires no intervention beyond normal CLI use
    And no verdict-schema or action-executor defect causes an unsafe action
    And every processed message has a reconstructable decision trail

  @audit
  Scenario: Logs and audit records reconstruct behavior
    Given the week-long run has completed
    When an operator investigates a selected message and control-plane change
    Then the correlation ID links the operational log entries
    And the audit log identifies the decision, action, and timestamp
    And the result can be explained without relying on operator memory

  @release
  Scenario: The release is tagged only after the exit criteria pass
    Given the full-week run and live acceptance evidence are approved
    When the maintainer prepares the release
    Then the version, package metadata, documentation, and test inventory agree
    And the maintainer tags v1.0.0
