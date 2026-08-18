"""KeywordClassifier: the dependency-free default local classifier (docs/DESIGN.md §9.1).

Self-registers under "keyword_heuristic" as an import side effect
(triggered by `spork.core.classify.__init__`, which every real caller
already imports via `from spork.core.classify import registry`) — so
`tiering.local_classifier = "keyword_heuristic"` just works out of the
box, with zero extra installs and zero per-caller wiring. Swapping to
a heavier technique (spaCy, a local embedding model) is adding a new
backend module behind the same `TextClassifier` Protocol, never
editing this one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from spork.core.classify.base import ClassificationResult
from spork.core.classify.registry import register
from spork.core.models import NormalizedMessage

# A reasonable, generic starting point — not tuned to any one person's
# mail (§9.1: "what scores well on one person's mail may not on
# another's"). Deliberately small; override entirely via the
# constructor rather than editing this default.
DEFAULT_CATEGORY_KEYWORDS: Mapping[str, Sequence[str]] = {
    "urgent": ("urgent", "asap", "immediately", "deadline", "action required"),
    "newsletter": ("unsubscribe", "newsletter", "view in browser"),
    "receipt": ("receipt", "invoice", "order confirmation", "payment received"),
    "banking": ("bank", "payment", "transaction", "expenses", "card", "transfer"),
    "technology": ("github", "repository", "pull request", "deployment", "commit"),
    "alert": ("alert", "warning", "failed", "unusual activity", "action required"),
    "notification": ("notification", "digest", "weekly report", "update"),
    "security": ("security", "sign-in", "verification", "password", "two-factor"),
}

# Returned when no configured category matched anything — a real,
# named answer ("nothing recognizable here"), not None or an
# arbitrarily-chosen first category.
DEFAULT_CATEGORY = "uncategorized"

_NOTIFICATION_HEADERS = frozenset({"list-unsubscribe", "precedence", "auto-submitted"})


class KeywordClassifier:
    """Scores message text and metadata against configured keyword lists.

    `category_keywords` maps a category name to the keywords/phrases
    that vote for it. Each category's score is the fraction of its own
    keyword list found (case-insensitive substring match) anywhere in
    `subject + body_text` — deliberately not a raw match count, so a
    category with many keywords isn't unfairly favored over one with
    few. Subject matches score higher than body-only matches, while
    notification headers and sender metadata provide independent local
    evidence. The winning category is whichever scored highest; ties go to
    whichever was listed first (dict order), a deterministic and
    documented tie-break rather than an arbitrary one.
    `default_category` is returned instead when every configured
    category scores exactly zero.
    """

    def __init__(
        self,
        category_keywords: Mapping[str, Sequence[str]] | None = None,
        default_category: str = DEFAULT_CATEGORY,
    ) -> None:
        self._category_keywords = (
            category_keywords if category_keywords is not None else DEFAULT_CATEGORY_KEYWORDS
        )
        self._default_category = default_category

    def classify(self, message: NormalizedMessage) -> ClassificationResult:
        subject = message.subject.casefold()
        body = message.body_text.casefold()
        scores: dict[str, float] = {}
        for category, keywords in self._category_keywords.items():
            if not keywords:
                scores[category] = 0.0
                continue
            signals = [
                1.0 if keyword.casefold() in subject else 0.6
                for keyword in keywords
                if keyword.casefold() in subject or keyword.casefold() in body
            ]
            scores[category] = min(1.0, max(signals, default=0.0) + 0.1 * max(0, len(signals) - 1))

        notification_score = self._notification_metadata_score(message)
        if "notification" in scores or notification_score > 0:
            scores["notification"] = max(scores.get("notification", 0.0), notification_score)

        best_category = max(scores, key=lambda category: scores[category], default=None)
        if best_category is None or scores[best_category] == 0.0:
            best_category = self._default_category

        return ClassificationResult(category=best_category, scores=scores)

    @staticmethod
    def _notification_metadata_score(message: NormalizedMessage) -> float:
        """Score standard bulk-mail headers and no-reply sender metadata."""
        headers = {name.casefold(): value.casefold() for name, value in message.headers.items()}
        if "list-unsubscribe" in headers:
            return 1.0
        if any(
            name in headers and headers[name] in {"bulk", "list", "auto-generated"}
            for name in _NOTIFICATION_HEADERS
        ):
            return 0.9
        if message.from_address.casefold().startswith(("no-reply@", "noreply@")):
            return 0.35
        return 0.0


# Import-time side effect, not a call site's responsibility — every
# real caller already does `from spork.core.classify import registry`,
# which runs this package's __init__.py (and therefore this module)
# first, same as any Python package import.
register("keyword_heuristic", KeywordClassifier)
