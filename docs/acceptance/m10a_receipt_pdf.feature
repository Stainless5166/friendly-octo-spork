# Offline acceptance specification for spork.core.receipts.pdf/archive
# (docs/ROADMAP.md M10, docs/DESIGN.md §9.5). Reusable independent of the
# rest of the receipt-archiving pipeline: this module only knows about a
# message, its attachments, and where to put the result -- nothing about
# rules, providers, or Tier 2. No live account, no network.

@m10 @receipt-pdf
Feature: Receipt PDF building and archiving
  A receipt message and its attachments combine into exactly one PDF,
  saved to a configured directory under a predictable filename.

  @no-attachments
  Scenario: A message with no attachments still produces one archived PDF
    Given a receipt message with no attachments
    When the message is built into a receipt PDF and archived
    Then exactly one PDF file exists in the output directory
    And the PDF has exactly one page containing the company and date

  @attachments
  Scenario: A PDF attachment is merged and an image attachment becomes its own page
    Given a receipt message with a one-page PDF attachment and an image attachment
    When the message is built into a receipt PDF and archived
    Then exactly one PDF file exists in the output directory
    And the archived PDF has 3 pages in cover, PDF-attachment, image-attachment order

  @unrenderable
  Scenario: An attachment of an unsupported type is named rather than dropped
    Given a receipt message with a CSV attachment
    When the message is built into a receipt PDF and archived
    Then exactly one PDF file exists in the output directory
    And the archived PDF names the CSV attachment's filename on its own page

  @filename
  Scenario: The archived filename is predictable from company, date, and message id
    Given a receipt message with no attachments
    When the message is built into a receipt PDF and archived
    Then the archived filename contains the date, the company, and the message id
