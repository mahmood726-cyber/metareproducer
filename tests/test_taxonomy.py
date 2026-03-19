"""Tests for pipeline.taxonomy — error classification and aggregation."""

import pytest


def test_classify_missing_pdf():
    """No PDF available → 'missing_pdf'."""
    from pipeline.taxonomy import classify_study_error

    result = classify_study_error(has_pdf=False, extraction=None)
    assert result == "missing_pdf"


def test_classify_extraction_failure():
    """PDF present but extraction is None or extracted_effect is None → 'extraction_failure'."""
    from pipeline.taxonomy import classify_study_error

    # No extraction object at all
    result1 = classify_study_error(has_pdf=True, extraction=None)
    assert result1 == "extraction_failure"

    # Extraction exists but effect is None
    result2 = classify_study_error(
        has_pdf=True,
        extraction={"extracted_effect": None, "matched": False, "match_tier": None},
    )
    assert result2 == "extraction_failure"


def test_classify_no_match():
    """PDF present, extraction has a value, but not matched → 'no_match'."""
    from pipeline.taxonomy import classify_study_error

    extraction = {
        "extracted_effect": 0.73,
        "matched": False,
        "match_tier": None,
    }
    result = classify_study_error(has_pdf=True, extraction=extraction)
    assert result == "no_match"


def test_classify_success():
    """PDF present, extraction matched → None (success)."""
    from pipeline.taxonomy import classify_study_error

    extraction = {
        "extracted_effect": 0.73,
        "matched": True,
        "match_tier": "direct_5pct",
    }
    result = classify_study_error(has_pdf=True, extraction=extraction)
    assert result is None


def test_aggregate_taxonomy():
    """Aggregation counts by category, adds 'success', and sets primary_error_source."""
    from pipeline.taxonomy import aggregate_errors

    study_errors = [
        None,               # success
        None,               # success
        "missing_pdf",
        "missing_pdf",
        "missing_pdf",
        "extraction_failure",
        "no_match",
    ]
    result = aggregate_errors(study_errors)

    assert result["success"]            == 2
    assert result["missing_pdf"]        == 3
    assert result["extraction_failure"] == 1
    assert result["no_match"]           == 1
    # Primary error source is the most common non-success category
    assert result["primary_error_source"] == "missing_pdf"
    # Total should equal input length
    total = (result["success"] + result.get("missing_pdf", 0)
             + result.get("extraction_failure", 0) + result.get("no_match", 0))
    assert total == 7
