"""Tests for pipeline/ctgov_extractor.py — AACT CT.gov integration."""

import pytest


# ---------------------------------------------------------------------------
# match_aact_effect
# ---------------------------------------------------------------------------

def test_match_aact_effect_hr():
    """AACT HR matches Cochrane value within 5%."""
    from pipeline.ctgov_extractor import match_aact_effect

    effects = [
        {
            "point_estimate": 0.74,
            "ci_lower": 0.65,
            "ci_upper": 0.85,
            "param_type": "Hazard Ratio (HR)",
            "method": "Cox",
        }
    ]
    result = match_aact_effect(effects, cochrane_mean=0.75, is_ratio=True)
    assert result is not None
    assert result["matched"] is True
    assert result["match_tier"].startswith("aact_")
    assert result["source"] == "aact"


def test_match_aact_effect_no_match():
    """AACT effect too far from Cochrane -> None."""
    from pipeline.ctgov_extractor import match_aact_effect

    effects = [
        {
            "point_estimate": 1.50,
            "ci_lower": 1.1,
            "ci_upper": 2.0,
            "param_type": "OR",
            "method": "logistic",
        }
    ]
    result = match_aact_effect(effects, cochrane_mean=0.75, is_ratio=True)
    assert result is None


def test_match_aact_effect_best_of_multiple():
    """When multiple AACT effects exist, pick closest match."""
    from pipeline.ctgov_extractor import match_aact_effect

    effects = [
        {
            "point_estimate": 0.90,
            "ci_lower": 0.7,
            "ci_upper": 1.1,
            "param_type": "HR",
            "method": "Cox",
        },
        {
            "point_estimate": 0.76,
            "ci_lower": 0.6,
            "ci_upper": 0.9,
            "param_type": "HR",
            "method": "Cox",
        },
    ]
    result = match_aact_effect(effects, cochrane_mean=0.75, is_ratio=True)
    assert result is not None
    assert abs(result["point_estimate"] - 0.76) < 0.01


def test_match_aact_effect_empty_list():
    """Empty effects list returns None."""
    from pipeline.ctgov_extractor import match_aact_effect

    result = match_aact_effect([], cochrane_mean=0.75, is_ratio=True)
    assert result is None


def test_match_aact_effect_none_point_estimate():
    """Effects with None point_estimate are skipped."""
    from pipeline.ctgov_extractor import match_aact_effect

    effects = [
        {
            "point_estimate": None,
            "ci_lower": 0.6,
            "ci_upper": 0.9,
            "param_type": "HR",
            "method": "Cox",
        }
    ]
    result = match_aact_effect(effects, cochrane_mean=0.75, is_ratio=True)
    assert result is None


def test_match_aact_effect_md():
    """Mean difference match works (non-ratio)."""
    from pipeline.ctgov_extractor import match_aact_effect

    effects = [
        {
            "point_estimate": -2.45,
            "ci_lower": -4.0,
            "ci_upper": -0.9,
            "param_type": "Mean Difference (Final Values)",
            "method": "ANCOVA",
        }
    ]
    result = match_aact_effect(effects, cochrane_mean=-2.50, is_ratio=False)
    assert result is not None
    assert result["matched"] is True
    assert result["match_tier"] == "aact_5pct"


def test_match_aact_effect_tier_10pct():
    """Effect within 10% but outside 5% gets aact_10pct tier."""
    from pipeline.ctgov_extractor import match_aact_effect

    # 0.82 vs 0.75 = 9.3% difference -> 10pct tier
    effects = [
        {
            "point_estimate": 0.82,
            "ci_lower": 0.6,
            "ci_upper": 1.0,
            "param_type": "HR",
            "method": "Cox",
        }
    ]
    result = match_aact_effect(effects, cochrane_mean=0.75, is_ratio=True)
    assert result is not None
    assert result["match_tier"] == "aact_10pct"


# ---------------------------------------------------------------------------
# PARAM_TYPE_MAP
# ---------------------------------------------------------------------------

def test_param_type_map():
    """PARAM_TYPE_MAP covers key effect types."""
    from pipeline.ctgov_extractor import PARAM_TYPE_MAP

    assert PARAM_TYPE_MAP["Hazard Ratio (HR)"] == "HR"
    assert PARAM_TYPE_MAP["Odds Ratio (OR)"] == "OR"
    assert PARAM_TYPE_MAP["Risk Ratio (RR)"] == "RR"
    assert PARAM_TYPE_MAP["Mean Difference (Final Values)"] == "MD"
    assert PARAM_TYPE_MAP["LS Mean Difference"] == "MD"


# ---------------------------------------------------------------------------
# Empty input handling
# ---------------------------------------------------------------------------

def test_batch_pmid_to_nct_empty():
    """batch_pmid_to_nct with empty list returns empty dict."""
    from pipeline.ctgov_extractor import batch_pmid_to_nct

    result = batch_pmid_to_nct(None, [])
    assert result == {}


def test_fetch_precomputed_effects_empty():
    """fetch_precomputed_effects with empty list returns empty dict."""
    from pipeline.ctgov_extractor import fetch_precomputed_effects

    result = fetch_precomputed_effects(None, [])
    assert result == {}


def test_fetch_raw_outcomes_empty():
    """fetch_raw_outcomes with empty list returns empty dict."""
    from pipeline.ctgov_extractor import fetch_raw_outcomes

    result = fetch_raw_outcomes(None, [])
    assert result == {}


# ---------------------------------------------------------------------------
# build_aact_lookup callable
# ---------------------------------------------------------------------------

def test_build_aact_lookup_exists():
    """build_aact_lookup function exists and is callable."""
    from pipeline.ctgov_extractor import build_aact_lookup

    assert callable(build_aact_lookup)


# ---------------------------------------------------------------------------
# get_connection
# ---------------------------------------------------------------------------

def test_get_connection_exists():
    """get_connection function exists and is callable."""
    from pipeline.ctgov_extractor import get_connection

    assert callable(get_connection)


# ---------------------------------------------------------------------------
# CT.gov REST API v2 fallback
# ---------------------------------------------------------------------------

def test_build_aact_lookup_via_api_exists():
    """build_aact_lookup_via_api function exists and is callable."""
    from pipeline.ctgov_extractor import build_aact_lookup_via_api

    assert callable(build_aact_lookup_via_api)


def test_build_aact_lookup_via_api_empty():
    """Empty PMID list returns empty dict without API calls."""
    from pipeline.ctgov_extractor import build_aact_lookup_via_api

    result = build_aact_lookup_via_api([])
    assert result == {}


def test_api_batch_pmid_to_nct_empty():
    """Empty PMID list returns empty dict without API calls."""
    from pipeline.ctgov_extractor import _api_batch_pmid_to_nct

    result = _api_batch_pmid_to_nct([])
    assert result == {}


def test_api_fetch_analyses_empty():
    """Empty NCT ID list returns empty dict without API calls."""
    from pipeline.ctgov_extractor import _api_fetch_analyses

    result = _api_fetch_analyses([])
    assert result == {}


@pytest.mark.skipif(
    not pytest.importorskip("urllib.request", reason="no network"),
    reason="network access required",
)
def test_api_batch_pmid_to_nct_live():
    """Live test: known PMID (EMPA-REG) maps to a valid NCT ID."""
    from pipeline.ctgov_extractor import _api_batch_pmid_to_nct

    result = _api_batch_pmid_to_nct(["26378978"])
    # PMID 26378978 is referenced by multiple studies (NCT01131676,
    # NCT03200860, etc.).  We just verify it maps to *some* NCT ID.
    assert "26378978" in result
    assert result["26378978"].startswith("NCT")


@pytest.mark.skipif(
    not pytest.importorskip("urllib.request", reason="no network"),
    reason="network access required",
)
def test_api_fetch_analyses_live():
    """Live test: NCT01131676 (EMPA-REG) has HR analyses."""
    from pipeline.ctgov_extractor import _api_fetch_analyses

    result = _api_fetch_analyses(["NCT01131676"])
    assert "NCT01131676" in result
    effects = result["NCT01131676"]
    assert len(effects) > 0
    # Should have at least one HR
    hr_effects = [e for e in effects if "Hazard" in e.get("param_type", "")]
    assert len(hr_effects) > 0
    # Known primary result: HR = 0.86
    hr_086 = [e for e in hr_effects if abs(e["point_estimate"] - 0.86) < 0.01]
    assert len(hr_086) > 0
