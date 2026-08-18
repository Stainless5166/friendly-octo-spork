@acceptance-local @m4
Feature: Local alert acceptance
  Injected alert components exercise VIP, Tier 2, and DBus fallback behavior
  without a desktop session or live daemon.

  @vip
  Scenario: A local VIP rule alerts with the action correlation
    Given a local M4 VIP message and an injected alerter
    When the local M4 message is processed by Tier 1
    Then the local M4 alerter received one alert
    And the local M4 alert title contains "vip_sender"

  @tier2
  Scenario: A high-urgency local Tier 2 action alerts
    Given a local M4 high-urgency recorded verdict and an injected alerter
    When the local M4 message is processed by Tier 2
    Then the local M4 action was applied
    And the local M4 alerter received one critical alert

  @dbus
  Scenario: A local DBus failure falls back to logging
    Given a local M4 desktop alerter whose notify-send runner fails
    When the local M4 alert is delivered
    Then the local M4 fallback received the alert
