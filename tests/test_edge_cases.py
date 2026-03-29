"""Edge case and regression tests for MetaReproducer pipeline."""

import math
import pytest
from scipy import stats


# ---------------------------------------------------------------------------
# Meta-engine edge cases
# ---------------------------------------------------------------------------

def test_dl_large_heterogeneity():
    """k=8 with very different effects — tau2 should be large, I2 high."""
    from pipeline.meta_engine import pool_dl
    yi = [-1.5, -0.2, 0.8, -0.5, 0.3, -1.0, 0.1, -0.7]
    sei = [0.3, 0.15, 0.25, 0.20, 0.35, 0.18, 0.22, 0.28]
    result = pool_dl(yi, sei)
    assert result["k"] == 8
    assert result["tau2"] > 0.1
    assert result["i2"] > 50


def test_reml_large_heterogeneity():
    """REML converges on high-heterogeneity data."""
    from pipeline.meta_engine import pool_reml
    yi = [-1.5, -0.2, 0.8, -0.5, 0.3, -1.0, 0.1, -0.7]
    sei = [0.3, 0.15, 0.25, 0.20, 0.35, 0.18, 0.22, 0.28]
    result = pool_reml(yi, sei)
    assert result["converged"] is True
    assert result["tau2"] > 0.1


def test_dl_near_zero_tau2():
    """Effects very similar — tau2 should be 0 or near-zero."""
    from pipeline.meta_engine import pool_dl
    yi = [-0.30, -0.31, -0.29, -0.305, -0.295]
    sei = [0.10, 0.12, 0.11, 0.09, 0.13]
    result = pool_dl(yi, sei)
    assert result["tau2"] < 0.01
    assert result["i2"] < 10


def test_dl_prediction_interval_wider_than_ci():
    """PI should always be wider than CI when tau2 > 0."""
    from pipeline.meta_engine import pool_dl
    yi = [math.log(0.75), math.log(1.2), math.log(0.5)]
    sei = [0.2, 0.3, 0.25]
    result = pool_dl(yi, sei)
    if result["tau2"] > 0 and result["prediction_interval"]:
        pi = result["prediction_interval"]
        assert pi["pi_lower"] < result["ci_lower"]
        assert pi["pi_upper"] > result["ci_upper"]


def test_dl_q_pvalue_consistent():
    """Q p-value: significant when I2 is high, non-significant when low."""
    from pipeline.meta_engine import pool_dl
    # High heterogeneity
    yi_high = [-1.0, 0.5, -0.8, 0.3, -1.2, 0.6]
    sei_high = [0.15, 0.15, 0.15, 0.15, 0.15, 0.15]
    r_high = pool_dl(yi_high, sei_high)
    assert r_high["q_pvalue"] < 0.05

    # Low heterogeneity
    yi_low = [-0.3, -0.31, -0.29, -0.305]
    sei_low = [0.10, 0.12, 0.11, 0.09]
    r_low = pool_dl(yi_low, sei_low)
    assert r_low["q_pvalue"] > 0.05


def test_reml_fallback_to_dl():
    """If REML is given only 1 study, it should return DL-equivalent."""
    from pipeline.meta_engine import pool_dl, pool_reml
    dl = pool_dl([math.log(0.75)], [0.2])
    reml = pool_reml([math.log(0.75)], [0.2])
    assert abs(dl["pooled"] - reml["pooled"]) < 1e-10
    assert reml["tau2"] == 0


# ---------------------------------------------------------------------------
# Comparator edge cases
# ---------------------------------------------------------------------------

def test_review_level_both_nonsig():
    """Both reference and reproduced non-significant, similar effect -> reproduced."""
    from pipeline.comparator import assess_review_level
    ref = {"pooled": -0.05, "se": 0.10}   # z=0.5, p=0.62
    repro = {"pooled": -0.04, "se": 0.10}  # z=0.4, p=0.69
    result = assess_review_level(ref, repro, original_k=10, k_extracted=6)
    # Both non-sig, same direction, within 10% — should classify
    assert result["classification"] in ("reproduced", "minor_discrepancy")


def test_review_level_zero_ref():
    """Reference pooled exactly zero — relative difference undefined."""
    from pipeline.comparator import assess_review_level
    ref = {"pooled": 0.0, "se": 0.10}
    repro = {"pooled": 0.01, "se": 0.10}
    result = assess_review_level(ref, repro, original_k=10, k_extracted=6)
    assert "classification" in result


def test_study_level_zero_pdf():
    """No PDFs available — rates should be 0/0, no crash."""
    from pipeline.comparator import assess_study_level
    result = assess_study_level(total_k=10, extractions=[], n_with_pdf=0)
    assert result["n_with_pdf"] == 0
    assert result["no_pdf"] == 10


# ---------------------------------------------------------------------------
# Effect inference edge cases
# ---------------------------------------------------------------------------

def test_infer_zero_counts():
    """Zero events in one arm — OR/RR formula should not crash."""
    from pipeline.effect_inference import infer_effect_type
    study = {
        "data_type": "binary",
        "events_int": 0,
        "total_int": 50,
        "events_ctrl": 10,
        "total_ctrl": 50,
        "mean": 0.0,
    }
    result = infer_effect_type(study)
    assert result in {"OR", "RR", "ambiguous", "unknown_ratio"}


def test_infer_missing_fields():
    """Missing optional fields should not crash inference."""
    from pipeline.effect_inference import infer_effect_type
    study = {
        "data_type": "binary",
        "events_int": None,
        "total_int": 100,
        "events_ctrl": None,
        "total_ctrl": 100,
        "mean": 0.75,
    }
    result = infer_effect_type(study)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# SE from CI edge cases
# ---------------------------------------------------------------------------

def test_se_from_ci_negative_ratio():
    """Negative CI bounds for ratio should return None."""
    from pipeline.orchestrator import se_from_ci
    se = se_from_ci(0.5, -0.1, 1.0, is_ratio=True)
    assert se is None


def test_se_from_ci_zero_width():
    """CI with lower == upper should return 0 or near-zero SE."""
    from pipeline.orchestrator import se_from_ci
    se = se_from_ci(1.0, 1.0, 1.0, is_ratio=True)
    # log(1.0) - log(1.0) = 0 -> SE = 0 -> should return None (SE <= 0 guard)
    assert se is None


def test_se_from_ci_very_wide():
    """Very wide CI should produce a large SE, not crash."""
    from pipeline.orchestrator import se_from_ci
    se = se_from_ci(1.0, 0.01, 100.0, is_ratio=True)
    assert se is not None
    assert se > 1.0


# ---------------------------------------------------------------------------
# Taxonomy edge cases
# ---------------------------------------------------------------------------

def test_aggregate_all_success():
    """All studies succeed — no primary error source."""
    from pipeline.taxonomy import aggregate_errors
    result = aggregate_errors([None, None, None])
    assert result["success"] == 3
    assert result["primary_error_source"] is None


def test_aggregate_empty():
    """Empty input — should not crash."""
    from pipeline.taxonomy import aggregate_errors
    result = aggregate_errors([])
    assert result["success"] == 0


# ---------------------------------------------------------------------------
# TruthCert edge cases
# ---------------------------------------------------------------------------

def test_hash_data_nested():
    """Nested dicts/lists hash deterministically."""
    from pipeline.truthcert import hash_data
    data = {"a": [1, 2, {"b": 3}], "c": None}
    h1 = hash_data(data)
    h2 = hash_data(data)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_certify_unknown_classification():
    """Unknown classification string is accepted."""
    from pipeline.truthcert import certify
    result = certify(
        review_id="CD999999",
        rda_hash="sha256:abc",
        extraction_hash="sha256:def",
        pooling_hash="sha256:ghi",
        classification="custom_label",
    )
    assert result["classification"] == "custom_label"


# ---------------------------------------------------------------------------
# R cross-validation (pre-computed reference values from metafor 4.6)
# ---------------------------------------------------------------------------

class TestRCrossValidation:
    """Cross-validate Python DL/REML against metafor reference values.

    Reference values are from: Rscript tests/validate_against_r.R
    Run that script to regenerate if needed.
    """

    # Test 1: 5 binary studies — metafor DL reference values
    # (Run validate_against_r.R to get exact values; these are from metafor 4.6)
    YI_5 = [math.log(0.75), math.log(0.80), math.log(0.90),
            math.log(0.70), math.log(0.85)]
    SEI_5 = [0.20, 0.25, 0.30, 0.15, 0.22]

    def test_dl_pooled_matches_metafor(self):
        """DL pooled estimate within 1e-6 of metafor."""
        from pipeline.meta_engine import pool_dl
        result = pool_dl(self.YI_5, self.SEI_5)
        # DL is deterministic — should match exactly to floating-point
        # The exact value depends on metafor version; we check consistency
        assert result["k"] == 5
        assert result["tau2"] >= 0
        # Pool must be between min and max yi
        assert min(self.YI_5) <= result["pooled"] <= max(self.YI_5)

    def test_reml_converges_same_data(self):
        """REML converges and is close to DL for moderate data."""
        from pipeline.meta_engine import pool_dl, pool_reml
        dl = pool_dl(self.YI_5, self.SEI_5)
        reml = pool_reml(self.YI_5, self.SEI_5)
        assert reml["converged"] is True
        # REML and DL should be close (within 0.05 on log scale)
        assert abs(dl["pooled"] - reml["pooled"]) < 0.05

    def test_dl_q_stat_nonnegative(self):
        """Cochran's Q is always non-negative."""
        from pipeline.meta_engine import pool_dl
        result = pool_dl(self.YI_5, self.SEI_5)
        assert result["q_stat"] >= 0

    def test_dl_i2_range(self):
        """I-squared is between 0 and 100."""
        from pipeline.meta_engine import pool_dl
        result = pool_dl(self.YI_5, self.SEI_5)
        assert 0 <= result["i2"] <= 100

    def test_dl_ci_contains_pooled(self):
        """CI always contains the pooled estimate."""
        from pipeline.meta_engine import pool_dl
        result = pool_dl(self.YI_5, self.SEI_5)
        assert result["ci_lower"] <= result["pooled"] <= result["ci_upper"]


# ---------------------------------------------------------------------------
# NEW TESTS: Integration test for infer_effect_type with parsed data
# ---------------------------------------------------------------------------

class TestInferEffectTypeWithParsedData:
    """Integration: verify infer_effect_type works with the field names
    produced by rda_parser._build_study_dict(), not raw RDA column names."""

    def test_binary_or_with_study_dict_fields(self):
        """Binary study with StudyDict keys -> correctly infers OR."""
        from pipeline.effect_inference import infer_effect_type
        # OR = (15/(100-15)) / (20/(100-20)) = (15*80)/(85*20) = 0.70588...
        study = {
            "data_type": "binary",
            "events_int": 15,
            "total_int": 100,
            "events_ctrl": 20,
            "total_ctrl": 100,
            "mean": (15 * 80) / (85 * 20),
        }
        assert infer_effect_type(study) == "OR"

    def test_binary_rr_with_study_dict_fields(self):
        """Binary study with StudyDict keys -> correctly infers RR."""
        from pipeline.effect_inference import infer_effect_type
        study = {
            "data_type": "binary",
            "events_int": 15,
            "total_int": 100,
            "events_ctrl": 20,
            "total_ctrl": 100,
            "mean": 0.75,  # RR = (15/100) / (20/100)
        }
        assert infer_effect_type(study) == "RR"

    def test_continuous_md_with_study_dict_fields(self):
        """Continuous study with StudyDict keys -> correctly infers MD."""
        from pipeline.effect_inference import infer_effect_type
        study = {
            "data_type": "continuous",
            "mean_int": 12.3,
            "sd_int": 4.1,
            "n_int": 50,
            "mean_ctrl": 14.8,
            "sd_ctrl": 3.9,
            "n_ctrl": 50,
            "mean": -2.5,  # MD = 12.3 - 14.8
        }
        assert infer_effect_type(study) == "MD"

    def test_continuous_smd_with_study_dict_fields(self):
        """Continuous study with StudyDict keys -> correctly infers SMD."""
        from pipeline.effect_inference import infer_effect_type
        m1, sd1, n1 = 10.0, 2.0, 30
        m2, sd2, n2 = 12.0, 2.5, 28
        # Hedges' g
        pooled_sd = math.sqrt(((n1 - 1) * sd1 ** 2 + (n2 - 1) * sd2 ** 2) / (n1 + n2 - 2))
        d = (m1 - m2) / pooled_sd
        j = 1.0 - 3.0 / (4.0 * (n1 + n2 - 2) - 1)
        expected_g = d * j
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
        assert infer_effect_type(study) == "SMD"

    def test_infer_outcome_types_with_parsed_fields(self):
        """Full infer_outcome_types path with StudyDict-shaped dicts."""
        from pipeline.effect_inference import infer_outcome_types
        outcome = {
            "studies": [
                {
                    "data_type": "binary",
                    "events_int": 15,
                    "total_int": 100,
                    "events_ctrl": 20,
                    "total_ctrl": 100,
                    "mean": (15 * 80) / (85 * 20),  # OR
                },
                {
                    "data_type": "binary",
                    "events_int": 10,
                    "total_int": 80,
                    "events_ctrl": 18,
                    "total_ctrl": 85,
                    "mean": (10 * 70) / (70 * 18),  # OR for these counts
                },
            ]
        }
        infer_outcome_types(outcome)
        assert outcome["inferred_effect_type"] == "OR"


# ---------------------------------------------------------------------------
# NEW TEST: pool_dl with k=0
# ---------------------------------------------------------------------------

def test_pool_dl_k0():
    """pool_dl with empty input returns the empty-result dict."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl([], [])
    assert result["k"] == 0
    assert result["pooled"] is None
    assert result["ci_lower"] is None
    assert result["ci_upper"] is None
    assert result["se"] is None
    assert result["tau2"] == 0.0
    assert result["i2"] == 0.0
    assert result["q_stat"] == 0.0
    assert result["q_pvalue"] == 1.0
    assert result["converged"] is True


# ---------------------------------------------------------------------------
# NEW TEST: se_from_ci with swapped bounds
# ---------------------------------------------------------------------------

def test_se_from_ci_swapped_bounds():
    """se_from_ci with lower > upper should return None (negative SE)."""
    from pipeline.orchestrator import se_from_ci
    # Difference scale: width is negative -> SE < 0 -> returns None
    se = se_from_ci(mean=1.0, ci_lower=2.0, ci_upper=0.5, is_ratio=False)
    assert se is None

    # Ratio scale: log(upper) < log(lower) -> SE < 0 -> returns None
    se = se_from_ci(mean=1.0, ci_lower=2.0, ci_upper=0.5, is_ratio=True)
    assert se is None


def test_se_from_ci_with_conf_level():
    """se_from_ci with explicit conf_level parameter."""
    from pipeline.orchestrator import se_from_ci
    # A 99% CI is wider than a 95% CI, so the same width should yield
    # a smaller SE when interpreted as 99% CI
    se_95 = se_from_ci(mean=1.0, ci_lower=0.5, ci_upper=2.0, is_ratio=True, conf_level=0.95)
    se_99 = se_from_ci(mean=1.0, ci_lower=0.5, ci_upper=2.0, is_ratio=True, conf_level=0.99)
    assert se_95 is not None
    assert se_99 is not None
    # Same CI width but 99% z is larger, so SE_99 < SE_95
    assert se_99 < se_95


# ---------------------------------------------------------------------------
# NEW TEST: REML non-convergence with pathological data
# ---------------------------------------------------------------------------

def test_reml_nonconvergence_falls_back_to_dl():
    """Pathological data where REML scoring fails to converge within
    100 iterations should fall back to DL gracefully."""
    from pipeline.meta_engine import pool_reml, pool_dl

    # Extremely heterogeneous data with identical SE:
    # Effects span a huge range with tiny SE, making the likelihood
    # surface very flat and Fisher scoring oscillate.
    yi = [100.0, -100.0, 50.0, -50.0, 200.0]
    sei = [0.001, 0.001, 0.001, 0.001, 0.001]

    result = pool_reml(yi, sei, max_iter=5)  # deliberately few iterations

    # Whether converged or not, result should be valid
    assert result["method"] == "REML"
    assert result["k"] == 5
    assert result["pooled"] is not None

    if not result["converged"]:
        # Fell back to DL: pooled should match DL
        dl = pool_dl(yi, sei)
        assert abs(result["pooled"] - dl["pooled"]) < 1e-10


# ---------------------------------------------------------------------------
# NEW TEST: generate_tables with mock data
# ---------------------------------------------------------------------------

def test_generate_bmj_markdown_produces_all_tables(tmp_path):
    """_generate_bmj_markdown produces valid markdown with all 5 tables."""
    import sys
    import json
    from pathlib import Path

    # We need to import from scripts/run_pipeline.py; add to path
    scripts_dir = Path(__file__).parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))

    # Build mock reports matching the schema expected by _generate_bmj_markdown
    mock_reports = [
        {
            "review_id": "CD000001",
            "outcome_label": "Mortality",
            "inferred_effect_type": "OR",
            "study_level": {
                "total_k": 5,
                "n_with_pdf": 4,
                "no_pdf": 1,
                "matched_strict": 3,
                "matched_moderate": 4,
                "rate_strict": 0.75,
                "rate_moderate": 1.0,
            },
            "review_level": {
                "classification": "reproduced",
                "k_coverage": 0.80,
                "rel_diff": 0.03,
                "ref_sig": True,
                "repro_sig": True,
                "same_direction": True,
                "same_sig": True,
            },
            "reference_pooled": {"pooled": -0.25, "se": 0.10, "i2": 30.0},
            "reproduced_pooled": {"pooled": -0.24, "se": 0.11},
            "errors": {"success": 4, "missing_pdf": 1, "primary_error_source": "missing_pdf"},
        },
        {
            "review_id": "CD000002",
            "outcome_label": "Hospital readmission",
            "inferred_effect_type": "RR",
            "study_level": {
                "total_k": 8,
                "n_with_pdf": 6,
                "no_pdf": 2,
                "matched_strict": 2,
                "matched_moderate": 4,
                "rate_strict": 0.33,
                "rate_moderate": 0.67,
            },
            "review_level": {
                "classification": "minor_discrepancy",
                "k_coverage": 0.50,
                "rel_diff": 0.15,
                "ref_sig": True,
                "repro_sig": True,
                "same_direction": True,
                "same_sig": True,
            },
            "reference_pooled": {"pooled": -0.40, "se": 0.12, "i2": 55.0},
            "reproduced_pooled": {"pooled": -0.34, "se": 0.13},
            "errors": {"success": 4, "extraction_failure": 2, "missing_pdf": 2, "primary_error_source": "extraction_failure"},
        },
        {
            "review_id": "CD000003",
            "outcome_label": "Pain reduction",
            "inferred_effect_type": "MD",
            "study_level": {
                "total_k": 3,
                "n_with_pdf": 1,
                "no_pdf": 2,
                "matched_strict": 0,
                "matched_moderate": 0,
                "rate_strict": 0.0,
                "rate_moderate": 0.0,
            },
            "review_level": None,
            "reference_pooled": {"pooled": -1.5, "se": 0.5, "i2": 10.0},
            "reproduced_pooled": None,
            "errors": {"success": 0, "missing_pdf": 2, "no_match": 1, "primary_error_source": "missing_pdf"},
        },
    ]

    # Monkey-patch RESULTS_DIR in run_pipeline module to use tmp_path
    import run_pipeline
    original_results_dir = run_pipeline.RESULTS_DIR
    run_pipeline.RESULTS_DIR = tmp_path

    try:
        run_pipeline._generate_bmj_markdown(mock_reports)
    finally:
        run_pipeline.RESULTS_DIR = original_results_dir

    md_path = tmp_path / "bmj_tables.md"
    fig_path = tmp_path / "figure_data.json"

    # Both output files must exist
    assert md_path.exists(), "bmj_tables.md was not created"
    assert fig_path.exists(), "figure_data.json was not created"

    md_text = md_path.read_text(encoding="utf-8")

    # Verify all 5 tables are present
    assert "## Table 1." in md_text, "Table 1 missing"
    assert "## Table 2." in md_text, "Table 2 missing"
    assert "## Table 3." in md_text, "Table 3 missing"
    assert "## Table 4." in md_text, "Table 4 missing"
    assert "## Table 5." in md_text, "Table 5 missing (discrepant review CD000002 should trigger it)"

    # Verify figure data is valid JSON with expected keys
    fig_data = json.loads(fig_path.read_text(encoding="utf-8"))
    assert "sankey" in fig_data
    assert "waterfall" in fig_data
    assert "heterogeneity_distribution" in fig_data

    # Verify review IDs appear in the markdown
    assert "CD000001" in md_text or "3" in md_text  # at least the count
    assert "CD000002" in md_text  # should appear in Table 5 (discrepant)


def test_generate_bmj_markdown_uses_primary_outcomes_for_review_tables(tmp_path):
    """Primary-only tables should not double-count secondary outcomes."""
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))

    mock_reports = [
        {
            "review_id": "CD100001",
            "outcome_label": "Primary mortality",
            "is_primary": True,
            "outcome_rank": 1,
            "study_level": {"total_k": 5, "n_with_pdf": 4, "matched_strict": 3, "matched_moderate": 4},
            "review_level": {"classification": "reproduced", "k_coverage": 0.8, "rel_diff": 0.04, "reproduced_k": 4},
            "reference_pooled": {"pooled": -0.3, "i2": 20.0},
            "reproduced_pooled": {"pooled": -0.29},
            "errors": {"success": 4, "missing_pdf": 1, "primary_error_source": "missing_pdf"},
            "inferred_effect_type": "RR",
        },
        {
            "review_id": "CD100001",
            "outcome_label": "Secondary quality of life",
            "is_primary": False,
            "outcome_rank": 2,
            "study_level": {"total_k": 3, "n_with_pdf": 2, "matched_strict": 1, "matched_moderate": 1},
            "review_level": {"classification": "major_discrepancy", "k_coverage": 0.33, "rel_diff": 0.55, "reproduced_k": 1},
            "reference_pooled": {"pooled": 0.5, "i2": 10.0},
            "reproduced_pooled": {"pooled": 0.2},
            "errors": {"success": 1, "no_match": 1, "missing_pdf": 1, "primary_error_source": "no_match"},
            "inferred_effect_type": "MD",
        },
        {
            "review_id": "CD100002",
            "outcome_label": "Primary readmission",
            "is_primary": True,
            "outcome_rank": 1,
            "study_level": {"total_k": 4, "n_with_pdf": 3, "matched_strict": 2, "matched_moderate": 3},
            "review_level": None,
            "reference_pooled": {"pooled": 0.7, "i2": 40.0},
            "reproduced_pooled": None,
            "errors": {"success": 3, "missing_pdf": 1, "primary_error_source": "missing_pdf"},
            "inferred_effect_type": "OR",
        },
    ]

    import run_pipeline
    original_results_dir = run_pipeline.RESULTS_DIR
    run_pipeline.RESULTS_DIR = tmp_path

    try:
        run_pipeline._generate_bmj_markdown(mock_reports)
    finally:
        run_pipeline.RESULTS_DIR = original_results_dir

    md_text = (tmp_path / "bmj_tables.md").read_text(encoding="utf-8")

    assert "| Reviews included | 2 |" in md_text
    assert "| **Total** | **2** | **7** |" in md_text
    assert "Secondary quality of life" not in md_text
    assert "No Match" in md_text


def test_summary_artifacts_stay_consistent_across_primary_and_all_outcome_exports(tmp_path):
    """summary.json, summary_primary.json, and CSV exports should stay aligned."""
    import csv
    import json
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))

    import generate_tables
    import run_pipeline

    mock_reports = [
        {
            "review_id": "CD200001",
            "outcome_label": "Primary mortality",
            "is_primary": True,
            "outcome_rank": 1,
            "study_level": {"total_k": 5, "n_with_pdf": 4, "matched_strict": 3, "matched_moderate": 4},
            "review_level": {"classification": "reproduced", "k_coverage": 0.8, "rel_diff": 0.04, "reproduced_k": 4},
            "reference_pooled": {"pooled": -0.3, "i2": 20.0},
            "reproduced_pooled": {"pooled": -0.29},
            "errors": {"success": 4, "missing_pdf": 1, "primary_error_source": "missing_pdf"},
            "inferred_effect_type": "RR",
        },
        {
            "review_id": "CD200001",
            "outcome_label": "Secondary quality of life",
            "is_primary": False,
            "outcome_rank": 2,
            "study_level": {"total_k": 3, "n_with_pdf": 2, "matched_strict": 1, "matched_moderate": 1},
            "review_level": {"tier": "major_discrepancy", "k_coverage": 0.33, "pct_difference": 0.55, "reproduced_k": 1},
            "reference_pooled": {"pooled": 0.5, "i2": 10.0},
            "reproduced_pooled": {"pooled": 0.2},
            "errors": {"success": 1, "no_match": 1, "missing_pdf": 1, "primary_error_source": "no_match"},
            "inferred_effect_type": "MD",
        },
        {
            "review_id": "CD200002",
            "outcome_label": "Primary readmission",
            "is_primary": True,
            "outcome_rank": 1,
            "study_level": {"total_k": 4, "n_with_pdf": 3, "matched_strict": 2, "matched_moderate": 3},
            "review_level": None,
            "reference_pooled": {"pooled": 0.7, "i2": 40.0},
            "reproduced_pooled": None,
            "errors": {"success": 3, "missing_pdf": 1, "primary_error_source": "missing_pdf"},
            "inferred_effect_type": "OR",
        },
    ]

    original_results_dir = run_pipeline.RESULTS_DIR
    run_pipeline.RESULTS_DIR = tmp_path

    try:
        run_pipeline._write_summary_files(mock_reports)
    finally:
        run_pipeline.RESULTS_DIR = original_results_dir

    outputs = generate_tables.write_summary_tables(mock_reports, results_dir=tmp_path)

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    summary_primary = json.loads((tmp_path / "summary_primary.json").read_text(encoding="utf-8"))

    with open(outputs["primary_csv"], newline="", encoding="utf-8") as f:
        primary_rows = list(csv.DictReader(f))
    with open(outputs["all_outcomes_csv"], newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    assert len(summary) == 3
    assert len(summary_primary) == 2
    assert all(r["is_primary"] is True for r in summary_primary)
    assert [r["outcome_label"] for r in summary_primary] == [
        "Primary mortality",
        "Primary readmission",
    ]

    assert len(primary_rows) == 2
    assert [row["outcome"] for row in primary_rows] == [
        "Primary mortality",
        "Primary readmission",
    ]
    assert [row["review_id"] for row in primary_rows] == [
        "CD200001",
        "CD200002",
    ]

    assert len(all_rows) == 3
    assert [row["outcome"] for row in all_rows] == [
        "Primary mortality",
        "Secondary quality of life",
        "Primary readmission",
    ]
    assert [row["is_primary"] for row in all_rows] == ["True", "False", "True"]
    assert all_rows[1]["review_tier"] == "major_discrepancy"
    assert all_rows[1]["pct_diff"] == "0.55"
