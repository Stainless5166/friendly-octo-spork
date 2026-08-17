# Offline acceptance specification for the Tier 2 receipt-extraction
# fallback (docs/ROADMAP.md M10, docs/DESIGN.md §9.5, §10.5). No live
# model call anywhere in this feature -- RecordedReceiptExtractionClient
# replays a fixture, the same "no live API call in the test run" shape
# m3_tier2.feature's own recorded/offline evidence uses.

@m10 @receipt-extraction-llm
Feature: Recorded Tier 2 receipt extraction
  A recorded extraction fixture stands in for a real Claude call,
  keyed by sender domain, so the receipt-archiving pipeline's Tier 2
  fallback is testable with no live account.

  @recorded
  Scenario: A recorded extraction is returned for its sender domain
    Given a recorded extraction of "New Vendor Inc" / "2026-08-01" for domain "newvendor.io"
    When a receipt from "newvendor.io" is extracted via the recorded client
    Then the recorded extraction is company "New Vendor Inc" dated "2026-08-01"

  @multiple-domains
  Scenario: Different domains route to their own recorded extraction
    Given a recorded extraction of "New Vendor Inc" / "2026-08-01" for domain "newvendor.io"
    And a recorded extraction of "Other Co" / "2026-08-02" for domain "otherco.example"
    When a receipt from "otherco.example" is extracted via the recorded client
    Then the recorded extraction is company "Other Co" dated "2026-08-02"

  @unrecorded
  Scenario: An unrecorded domain fails clearly instead of guessing
    Given a recorded extraction of "New Vendor Inc" / "2026-08-01" for domain "newvendor.io"
    When a receipt from "unrecorded.example" is extracted via the recorded client
    Then the recorded client reports no extraction is available for that domain
