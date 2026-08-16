# Manual/live acceptance specification for M5.

@manual @requires-daemon @m5
Feature: Daemon and CLI control surface
  The CLI controls a running daemon over its Unix socket and records
  control-plane changes without disrupting message processing.

  Background:
    Given sporkd is running with a dedicated test configuration
    And the control socket has restrictive user-only permissions
    And the daemon has at least one safe acceptance rule

  @status
  Scenario: Status reports the running daemon
    When the operator runs "spork status"
    Then the command reports that the daemon is reachable
    And it reports the daemon start time and pause state
    And it exits successfully without printing a traceback

  @pause
  Scenario: Pause and resume control message acquisition
    When the operator runs "spork pause"
    Then the daemon acknowledges the paused state
    And no new source poll begins while paused
    When the operator runs "spork resume"
    Then the daemon acknowledges the resumed state
    And source polling continues
    And both control-plane changes are present in the audit log

  @reload
  Scenario: Rules changes take effect without daemon restart
    Given the operator edits the rules file and adds a new enabled rule
    When the operator requests a rules reload
    Then the daemon reports the new rule count
    And the next acquisition cycle uses the new rules
    And a malformed reload leaves the previous valid rules active

  @config
  Scenario: Config edits require restart rather than unsafe live mutation
    When the operator saves a valid config edit
    Then the merged config is validated
    And the command instructs the operator to restart sporkd
    And the running daemon continues using its existing composed backends

  @logs
  Scenario: Logs reconstruct a control-plane change
    When the operator runs "spork logs" after a pause, resume, reload, or reclassify
    Then the command displays the control-plane audit event
    And the event includes its timestamp and detail
