@m11 @local
Feature: Classification accumulation and action decisions
  Classification stages contribute evidence before a separate decider maps
  that evidence to one mailbox and any number of tags.

  @merge
  Scenario: Classification stages merge duplicate names by greatest score
    Given a message has no classifications
    When the sender-domain stage adds "banking" with score 100
    And the keyword stage adds "banking" with score 80
    And the keyword stage adds "alert" with score 80
    Then the classifications contain "banking" with score 100
    And the classifications contain "alert" with score 80
    And "banking" appears only once

  @thresholds
  Scenario: The decider selects one mailbox and additive tags by policy thresholds
    Given the classifications are "banking" 100, "alert" 80, and "security" 20
    And the mailbox threshold for "banking" is 70
    And the tag threshold for "alert" is 70
    And the tag threshold for "security" is 50
    When the decider evaluates the classifications
    Then the selected mailbox is "Banking and Finance"
    And the selected tags contain only "Alert"

  @thresholds
  Scenario: A low-confidence classification remains evidence but causes no action
    Given the classifications are "security" 20
    And the tag threshold for "security" is 50
    When the decider evaluates the classifications
    Then no mailbox is selected
    And no tags are selected
    And the classification evidence is retained
