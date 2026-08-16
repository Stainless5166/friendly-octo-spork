# Manual acceptance specification.
#
# These scenarios require a dedicated Fastmail test account and are not run
# by pytest or CI. They define the live evidence required before M1 is closed.
# Do not place addresses, tokens, message bodies, or mailbox contents here.

@manual @requires-fastmail @m1
Feature: Live JMAP message ingestion
  Spork receives new mail through JMAP push, uses polling when push is
  unavailable, and never advances its durable cursor past unprocessed mail.

  Background:
    Given a dedicated Fastmail test account is configured through SecretSpec
    And the JMAP API token is available as "JMAP_API_TOKEN"
    And the account has an Inbox-role mailbox
    And the daemon uses JmapProvider with a short test polling interval
    And the daemon uses a rule that ignores the acceptance message
    And the acceptance state database is empty or has been backed up

  @baseline
  Scenario: First start establishes a safe Inbox baseline
    Given the Inbox contains existing messages
    When sporkd starts and completes JMAP session discovery
    Then sporkd reports readiness only after the provider and cursor are composed
    And the current Email state is stored as the candidate baseline cursor
    And no pre-existing Inbox message is processed by the acceptance rule

  @push
  Scenario: A newly delivered message wakes the daemon through push
    Given sporkd has an acknowledged Email cursor
    When a new acceptance message is delivered to the Inbox
    Then an EventSource EmailDelivery or Email event is received for the account
    And the message is fetched through Email/changes and Email/get
    And the acceptance rule processes the message exactly once
    And the new Email cursor is stored after processing completes

  @fallback
  Scenario: Polling continues while EventSource push is disconnected
    Given sporkd has an acknowledged Email cursor
    When the EventSource connection is interrupted
    Then the push trigger reports a transient disconnect after its backoff delay
    And the polling source fetches changes using the shared candidate cursor
    When the EventSource connection becomes available again
    And the next source cycle runs
    Then the push source is retried before the polling source
    And a relevant push event wakes the source when one arrives

  @cursor-safety
  Scenario: A failed batch remains replayable after restart
    Given sporkd has an acknowledged Email cursor
    And a batch contains two acceptance messages
    When processing the first message fails before the batch completes
    Then the candidate Email cursor is not persisted
    When sporkd restarts
    Then it requests changes from the previous acknowledged cursor
    And the failed batch is available for replay

  @network-recovery
  Scenario: A forced network outage does not silently lose new mail
    Given sporkd is processing the dedicated acceptance account
    When network access is blocked for the configured outage window
    And network access is restored
    Then polling continues during the outage
    And push is retried with the configured backoff
    And a message delivered before or during the outage is eventually fetched
    And its cursor is acknowledged only after processing completes
