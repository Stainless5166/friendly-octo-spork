"""Verdict validation against a deployment's configured mailbox/category
set (docs/DESIGN.md §10.2).

`Verdict` (spork.core.llm.base) proves shape; it can't prove that a
category or mailbox actually exists in *this* deployment's
`config.toml`/JMAP mailbox state — pydantic has no access to that at
parse time. This module closes that gap as one pure function.
"""

from __future__ import annotations

from collections.abc import Sequence

from spork.core.llm.base import Verdict


class VerdictValidationError(Exception):
    """Raised when a Verdict's category or suggested_action.mailbox
    falls outside this deployment's configured closed set.

    An out-of-set value from the model is treated as a schema failure
    (docs/DESIGN.md §10), not silently applied — one catchable type,
    same convention as every other module boundary in spork.core.
    """


def validate_verdict(
    verdict: Verdict,
    *,
    allowed_categories: Sequence[str],
    allowed_mailboxes: Sequence[str],
) -> Verdict:
    """Check `verdict` against this deployment's configured sets.

    Returns `verdict` unchanged on success — never coerces or
    truncates a bad value into a valid one, since a deployment-specific
    mismatch should stop the pipeline, not get silently rewritten.
    `suggested_action.mailbox` is only checked when set (`None` for
    `ignore`, per `rules.schema.Action`'s docstring).
    """
    if verdict.category not in allowed_categories:
        raise VerdictValidationError(
            f"verdict category {verdict.category!r} is not in the configured "
            f"category set: {sorted(allowed_categories)}"
        )

    mailbox = verdict.suggested_action.mailbox
    if mailbox is not None and mailbox not in allowed_mailboxes:
        raise VerdictValidationError(
            f"suggested_action.mailbox {mailbox!r} is not in the configured "
            f"mailbox set: {sorted(allowed_mailboxes)}"
        )

    return verdict
