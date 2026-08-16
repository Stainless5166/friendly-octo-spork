"""Step scaffolding for M10's receipt-archiving acceptance scenarios.

Deliberately @wip (docs/acceptance/environment.py skips @wip scenarios
by default, same mechanism as @manual but for "not built yet" rather
than "needs a live account" — see m10_receipt_archiving.feature's own
header comment and docs/ROADMAP.md M10).

Every binding below raises NotImplementedError instead of importing
anything from a not-yet-existing `spork.core.receipts` package: behave
imports every file under `steps/` at startup, for every feature, so an
import of a module that doesn't exist yet would break discovery for
the whole acceptance suite, not just this one @wip feature. Once each
real module lands (attachment fetching, the known-sender registry,
deterministic + Tier 2 extraction, PDF building, archiving), replace
the corresponding stub here with a real binding against it — same
incremental order as the ROADMAP checklist, not one big rewrite at the
end.
"""

from __future__ import annotations

from typing import Any

from behave import given, then, when

_NOT_BUILT = (
    "spork.core.receipts is not implemented yet — see docs/ROADMAP.md M10 "
    "and docs/DESIGN.md §9.5 for the planned design this scenario exercises."
)


@given("a rules file with a rule that recognizes automatic-payment receipts")
def rules_file_recognizes_receipts(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@given("a receipt archive output directory is configured")
def receipt_archive_output_dir_configured(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@given('the known-senders registry is seeded with "{domain}" as "{company}"')
def known_senders_registry_seeded(context: Any, domain: str, company: str) -> None:
    raise NotImplementedError(_NOT_BUILT)


@given('a receipt email from "{domain}" with one PDF invoice attachment')
def receipt_email_with_pdf_attachment(context: Any, domain: str) -> None:
    raise NotImplementedError(_NOT_BUILT)


@given('a receipt email from the unrecognized domain "{domain}"')
def receipt_email_from_unrecognized_domain(context: Any, domain: str) -> None:
    raise NotImplementedError(_NOT_BUILT)


@given('"{domain}" was learned as "{company}" by an earlier Tier 2 call')
def sender_was_previously_learned(context: Any, domain: str, company: str) -> None:
    raise NotImplementedError(_NOT_BUILT)


@given('a receipt email from "{domain}" with no attachments')
def receipt_email_with_no_attachments(context: Any, domain: str) -> None:
    raise NotImplementedError(_NOT_BUILT)


@given('a receipt email from "{domain}" with a PDF attachment and an image attachment')
def receipt_email_with_two_attachments(context: Any, domain: str) -> None:
    raise NotImplementedError(_NOT_BUILT)


@given("a message that does not match the receipt rule")
def message_not_matching_receipt_rule(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@given("the configured output directory cannot be written to")
def output_directory_unwritable(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@when("the message is processed by Tier 1")
def message_processed_by_tier1(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@when('a second receipt email from "{domain}" is processed by Tier 1')
def second_message_processed_by_tier1(context: Any, domain: str) -> None:
    raise NotImplementedError(_NOT_BUILT)


@when("a known-sender receipt email is processed by Tier 1")
def known_sender_message_processed_by_tier1(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then(
    'the message is tagged "receipt", "company:{company}", '
    'and a "date:" tag matching the invoice date'
)
def message_tagged_from_invoice_date(context: Any, company: str) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then(
    "a single combined PDF containing the message and its attachment "
    "is saved to the configured output directory"
)
def combined_pdf_with_attachment_saved(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then("no Tier 2 call is made")
def no_tier2_call_is_made(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then("exactly one Tier 2 receipt-extraction call is made")
def exactly_one_tier2_call_is_made(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then(
    'the message is tagged "receipt", "company:{company}", '
    'and a "date:" tag matching the extracted date'
)
def message_tagged_from_extracted_date(context: Any, company: str) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then("a single combined PDF is saved to the configured output directory")
def combined_pdf_saved(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then('"{domain}" is recorded in the known-senders registry as "{company}"')
def sender_recorded_in_registry(context: Any, domain: str, company: str) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then("the message is tagged and archived without any Tier 2 call")
def message_tagged_and_archived_without_tier2(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then(
    "a single PDF built from the message content alone is saved to the configured output directory"
)
def pdf_from_message_content_alone_saved(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then("exactly one PDF file is saved to the configured output directory")
def exactly_one_pdf_file_saved(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then("that PDF contains the message content followed by both attachments in order")
def pdf_contains_message_then_attachments_in_order(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then("no PDF is archived")
def no_pdf_is_archived(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then("the message is handled by its normal matching rule instead")
def message_handled_by_normal_rule(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then("the failure is reported without a raw traceback")
def failure_reported_without_traceback(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then("the message is not marked processed")
def message_not_marked_processed(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)


@then("the next acquisition cycle can retry the message")
def next_cycle_can_retry(context: Any) -> None:
    raise NotImplementedError(_NOT_BUILT)
