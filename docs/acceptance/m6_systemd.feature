# Manual/live acceptance specification for M6.

@manual @requires-systemd-user @m6
Feature: Systemd user service operation
  Spork installs as a systemd user service without embedding secrets in
  the unit and reports useful startup health.

  Background:
    Given the package or repository installation is available
    And SecretSpec credentials are configured outside the unit file

  @install
  Scenario: The service installs and starts at user login
    When the operator runs "spork install-service"
    Then the unit is written to the user service directory
    And systemd reloads the user manager
    And the service is enabled and started
    And the unit reports Type=notify and Restart=on-failure

  @secrets
  Scenario: The unit contains no secret material
    When the installed unit file is inspected
    Then it contains no API token or model-provider key
    And sporkd resolves secrets through SecretSpec at startup

  @readiness
  Scenario: Systemd receives daemon readiness
    When sporkd completes backend composition and starts its control socket
    Then systemd receives READY=1
    And the service is reported active
    And a JMAP authentication failure prevents false readiness

  @doctor
  Scenario: Doctor reports configuration and service health
    When the operator runs "spork doctor"
    Then secrets, config, provider, LLM, alerter, rules, and service checks are reported independently
    And a failed check does not suppress the remaining checks
    And no raw traceback is printed

  @restart
  Scenario: A crashed daemon is restarted by systemd
    When sporkd exits unexpectedly
    Then systemd restarts it according to Restart=on-failure
    And the daemon resumes from its last acknowledged JMAP cursor
