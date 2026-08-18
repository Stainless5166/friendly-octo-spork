# Offline/local acceptance specification for M6.

@local @m6
Feature: Local systemd boundaries
  Systemd integration is checked at its file, subprocess, doctor, and
  sd_notify boundaries without requiring a user manager or JMAP.

  Scenario: The service unit contains no secret material
    When the local M6 operator inspects the service unit template
    Then the local M6 unit is notify-based and contains no secret values

  Scenario: Service installation uses the expected systemctl calls
    When the local M6 operator installs a unit with a fake systemctl runner
    Then the local M6 unit is written and systemctl receives reload and enable calls

  Scenario: Doctor reports independent local checks
    Given a local M6 doctor environment with an invalid config
    When the local M6 operator runs "spork doctor"
    Then the local M6 doctor reports every check without a traceback

  Scenario: Daemon readiness is delivered over a local notify socket
    When the local M6 operator listens on a temporary notify socket
    Then the local M6 readiness datagram is READY=1
