# Offline acceptance specification for the two new Provider capabilities
# receipt archiving needs (docs/ROADMAP.md M10, docs/DESIGN.md §9.5):
# fetching a message's attachments, and applying free-form per-message
# keywords. Exercised against FileProvider, which has no live-network
# blocker at all -- JmapProvider's own equivalents stay settled-shape
# NotImplementedError stubs, covered by pytest
# (tests/core/providers/jmap/), not repeated here.

@m10 @receipt-provider-capabilities
Feature: Attachment fetching and keyword tagging as Provider capabilities
  A Provider can resolve a message's raw attachments and apply
  free-form keywords to it, independent of any receipt-specific logic.

  @attachments
  Scenario: A message's attachments are resolved from the provider
    Given a FileProvider fixture with a message that has one PDF attachment
    When the attachment fetcher resolves that message's attachments
    Then exactly one attachment named "invoice.pdf" is returned

  @no-attachments
  Scenario: A message with no attachments resolves to none
    Given a FileProvider fixture with a message that has no attachments
    When the attachment fetcher resolves that message's attachments
    Then no attachments are returned

  @keywords
  Scenario: Applied keywords are recorded for later inspection
    Given a FileProvider fixture with one message
    When the keyword applier applies "receipt" and "company:Acme Cloud" to that message
    Then the keywords log records "receipt" and "company:Acme Cloud" for that message
