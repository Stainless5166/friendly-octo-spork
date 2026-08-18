# Offline/local acceptance specification for M5.

@local @m5
Feature: Local daemon and CLI control surface
  The local control surface exercises the real Unix-socket and CLI APIs
  without requiring a live JMAP account.

  Scenario: Status reports a locally served daemon
    Given a local M5 daemon control socket and temporary FileProvider config
    When the local M5 operator runs "spork status"
    Then the local M5 status command succeeds and reports a running daemon

  Scenario: Pause and resume update daemon state
    Given a local M5 daemon control socket and temporary FileProvider config
    When the local M5 operator runs "spork pause" and then "spork resume"
    Then the local M5 daemon state records pause and resume

  Scenario: Rules reload accepts a valid edit and rejects a malformed edit
    Given a local M5 daemon control socket and temporary FileProvider config
    When the local M5 operator reloads a valid rules edit
    Then the local M5 reload reports the new rule count
    When the local M5 operator reloads malformed rules
    Then the local M5 reload fails without changing the last valid rules

  Scenario: Config validation tells the operator to restart
    Given a valid local M5 user config and a temporary editor
    When the local M5 operator runs "spork config edit"
    Then the local M5 config command succeeds and instructs a daemon restart

  Scenario: Logs show a local control-plane audit entry
    Given a local M5 config with a control-plane audit entry
    When the local M5 operator runs "spork logs"
    Then the local M5 logs command displays the audit event without a traceback
