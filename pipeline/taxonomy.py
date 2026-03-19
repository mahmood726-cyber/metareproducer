"""
Error Taxonomy — pipeline/taxonomy.py

Classify individual study extraction errors and aggregate counts across
a review.

Error categories
----------------
missing_pdf         — study PDF was not obtained
extraction_failure  — PDF present but no effect could be extracted
no_match            — effect extracted but does not match Cochrane value
(None)              — success: matched within tolerance

Aggregation adds:
success             — count of None entries
primary_error_source— most frequent non-success category (or None)

Public API
----------
classify_study_error(has_pdf, extraction) -> str | None
aggregate_errors(study_errors)            -> dict
"""

from __future__ import annotations

from collections import Counter
from typing import Optional


# ---------------------------------------------------------------------------
# Eight recognised error categories (None = success)
# ---------------------------------------------------------------------------
CATEGORIES: list[str] = [
    "missing_pdf",
    "extraction_failure",
    "no_match",
    # Five further reserved categories for future use
    "format_error",
    "ambiguous_unit",
    "sign_flip",
    "scale_error",
    "other",
]


def classify_study_error(
    has_pdf: bool,
    extraction: Optional[dict],
) -> Optional[str]:
    """Classify a single study extraction outcome.

    Parameters
    ----------
    has_pdf    : True if the study PDF was obtained
    extraction : extraction result dict, or None if extraction was not run.
                 Expected keys: extracted_effect, matched, match_tier

    Returns
    -------
    None              — success (matched)
    "missing_pdf"     — PDF not available
    "extraction_failure" — PDF present but extracted_effect is None
    "no_match"        — extracted but did not match Cochrane value
    """
    if not has_pdf:
        return "missing_pdf"

    if extraction is None:
        return "extraction_failure"

    if extraction.get("extracted_effect") is None:
        return "extraction_failure"

    if extraction.get("matched", False):
        return None   # success

    return "no_match"


def aggregate_errors(study_errors: list[Optional[str]]) -> dict:
    """Count error categories across all studies in a review.

    Parameters
    ----------
    study_errors : list of outputs from classify_study_error(), i.e.
                   each element is a category string or None (success)

    Returns
    -------
    dict with:
        success               — count of None entries
        <category>            — count for each category that appears
        primary_error_source  — most frequent non-success category, or None
    """
    counts: Counter[str] = Counter()
    success_count = 0

    for err in study_errors:
        if err is None:
            success_count += 1
        else:
            counts[err] += 1

    result: dict = {"success": success_count}
    result.update(dict(counts))

    if counts:
        primary = counts.most_common(1)[0][0]
    else:
        primary = None

    result["primary_error_source"] = primary
    return result
