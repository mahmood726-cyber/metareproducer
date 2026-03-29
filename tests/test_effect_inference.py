"""Tests for pipeline.effect_inference — effect type inference from raw data."""

import math
import pytest


# ---------------------------------------------------------------------------
# Helper: compute expected SMD (Hedges' g) for the continuous test
# ---------------------------------------------------------------------------
def _expected_smd(m1, sd1, n1, m2, sd2, n2):
    """Hedges' g with correction j = 1 - 3 / (4*(n1+n2-2) - 1)."""
    pooled_sd = math.sqrt(((n1 - 1) * sd1 ** 2 + (n2 - 1) * sd2 ** 2) / (n1 + n2 - 2))
    d = (m1 - m2) / pooled_sd
    j = 1.0 - 3.0 / (4.0 * (n1 + n2 - 2) - 1)
    return d * j


# ---------------------------------------------------------------------------
# Unit tests for individual helpers
# ---------------------------------------------------------------------------

def test_infer_binary_or():
    """OR = (15*80) / (85*20) = 0.7059… → inferred OR."""
    from pipeline.effect_inference import infer_effect_type

    study = {
        "data_type": "binary",
        "events_int": 15,
        "total_int": 100,
        "events_ctrl": 20,
        "total_ctrl": 100,
        "mean": (15 * 80) / (85 * 20),   # OR = 0.70588…
    }
    result = infer_effect_type(study)
    assert result == "OR"


def test_infer_binary_rr():
    """RR = (15/100) / (20/100) = 0.75 → inferred RR."""
    from pipeline.effect_inference import infer_effect_type

    study = {
        "data_type": "binary",
        "events_int": 15,
        "total_int": 100,
        "events_ctrl": 20,
        "total_ctrl": 100,
        "mean": 0.75,   # matches RR exactly
    }
    result = infer_effect_type(study)
    assert result == "RR"


def test_infer_continuous_md():
    """MD = 12.3 - 14.8 = -2.5 → inferred MD."""
    from pipeline.effect_inference import infer_effect_type

    study = {
        "data_type": "continuous",
        "mean_int": 12.3,
        "sd_int": 4.1,
        "n_int": 50,
        "mean_ctrl": 14.8,
        "sd_ctrl": 3.9,
        "n_ctrl": 50,
        "mean": -2.5,
    }
    result = infer_effect_type(study)
    assert result == "MD"


def test_infer_continuous_smd():
    """Hedges' g for given parameters → inferred SMD."""
    from pipeline.effect_inference import infer_effect_type

    m1, sd1, n1 = 10.0, 2.0, 30
    m2, sd2, n2 = 12.0, 2.5, 28
    expected_g = _expected_smd(m1, sd1, n1, m2, sd2, n2)

    study = {
        "data_type": "continuous",
        "mean_int": m1,
        "sd_int": sd1,
        "n_int": n1,
        "mean_ctrl": m2,
        "sd_ctrl": sd2,
        "n_ctrl": n2,
        "mean": expected_g,
    }
    result = infer_effect_type(study)
    assert result == "SMD"


def test_infer_giv_only():
    """GIV-only data → 'unknown_ratio' regardless of mean value."""
    from pipeline.effect_inference import infer_effect_type

    study = {
        "data_type": "giv_only",
        "mean": -0.28,
    }
    result = infer_effect_type(study)
    assert result == "unknown_ratio"


def test_infer_ambiguous():
    """Mean = 0.50 does not match OR≈0.706 or RR=0.75 — should not crash."""
    from pipeline.effect_inference import infer_effect_type

    study = {
        "data_type": "binary",
        "events_int": 15,
        "total_int": 100,
        "events_ctrl": 20,
        "total_ctrl": 100,
        "mean": 0.50,   # matches neither OR nor RR
    }
    result = infer_effect_type(study)
    # Should return one of the recognised strings (ambiguous or a type label)
    assert result in {"OR", "RR", "MD", "SMD", "ambiguous", "unknown_ratio"}


def test_infer_outcome_types():
    """Majority-vote across two binary studies sets outcome['inferred_effect_type']."""
    from pipeline.effect_inference import infer_outcome_types

    outcome = {
        "studies": [
            {
                "data_type": "binary",
                "events_int": 15,
                "total_int": 100,
                "events_ctrl": 20,
                "total_ctrl": 100,
                "mean": (15 * 80) / (85 * 20),   # OR
            },
            {
                "data_type": "binary",
                "events_int": 10,
                "total_int": 80,
                "events_ctrl": 18,
                "total_ctrl": 85,
                "mean": (10 * 67) / (70 * 18),   # OR for these counts
            },
        ]
    }
    infer_outcome_types(outcome)
    assert "inferred_effect_type" in outcome
    assert outcome["inferred_effect_type"] == "OR"
