"""Regression test for P0-1: field-name contract between rda_parser and effect_inference.

Background
----------
review-findings.md (P0-1) documented that `infer_effect_type()` was reading
RDA raw column names ("Experimental.cases", "Experimental.N", etc.) while the
production caller passes StudyDicts produced by `rda_parser._build_study_dict()`,
which renames those fields to `events_int`, `total_int`, `mean_int`, `sd_int`,
`n_int`, `mean_ctrl`, `sd_ctrl`, `n_ctrl`. The mismatch silently classified
every study as "unknown_ratio", which in turn flipped `is_ratio=True` for ALL
outcomes, log-transforming mean differences before pooling.

The unit tests for `infer_effect_type` masked this by constructing dicts with
the raw RDA column names directly; no test exercised the full
parse_rows -> infer_outcome_types contract.

This module pins the contract: parsing a binary outcome through `parse_rows`
and feeding the resulting outcome dict to `infer_outcome_types` must produce a
ratio classification (OR/RR), and a continuous outcome must produce MD/SMD.
A regression to the old key names will set inferred_effect_type to
"unknown_ratio" and these assertions will fail.
"""

from __future__ import annotations

from pipeline.effect_inference import infer_outcome_types, infer_effect_type
from pipeline.orchestrator import _is_ratio_type
from pipeline.rda_parser import parse_rows


# ---------------------------------------------------------------------------
# Binary outcome: parse_rows -> infer_outcome_types must yield OR or RR
# ---------------------------------------------------------------------------

def test_binary_outcome_classified_via_parsed_studydict():
    """Full parse_rows -> infer_outcome_types path must NOT yield unknown_ratio
    for a well-formed binary outcome.

    With events 15/100 vs 20/100, OR = (15*80)/(85*20) = 0.7059, so when the
    Cochrane reported Mean is 0.7059 the inference engine should return "OR".
    Under the P0-1 bug, every study would be classified "unknown_ratio" because
    `infer_effect_type` would read RDA-style keys that no longer exist on the
    StudyDict.
    """
    or_value = (15 * 80) / (85 * 20)  # 0.70588...
    rows = [
        {
            "Study": "Smith 2005", "Study.year": 2005,
            "Analysis.name": "All-cause mortality",
            "Mean": or_value, "CI.start": 0.55, "CI.end": 0.92,
            "Experimental.cases": 15, "Experimental.N": 100,
            "Control.cases": 20, "Control.N": 100,
            "Experimental.mean": None, "Experimental.SD": None,
            "Control.mean": None, "Control.SD": None,
        },
        {
            "Study": "Jones 2008", "Study.year": 2008,
            "Analysis.name": "All-cause mortality",
            "Mean": or_value, "CI.start": 0.50, "CI.end": 0.95,
            "Experimental.cases": 15, "Experimental.N": 100,
            "Control.cases": 20, "Control.N": 100,
            "Experimental.mean": None, "Experimental.SD": None,
            "Control.mean": None, "Control.SD": None,
        },
    ]

    review = parse_rows("CD000001", rows, min_year=None)
    assert len(review["outcomes"]) == 1
    outcome = review["outcomes"][0]
    assert outcome["data_type"] == "binary"

    # Sanity: the StudyDicts coming out of parse_rows must use the renamed keys.
    study = outcome["studies"][0]
    assert "events_int" in study and study["events_int"] == 15
    assert "total_int" in study and study["total_int"] == 100
    assert "Experimental.cases" not in study, (
        "rda_parser must rename raw RDA columns to StudyDict keys"
    )

    # Per-study inference must succeed on the StudyDict shape.
    per_study = infer_effect_type(study)
    assert per_study != "unknown_ratio", (
        f"infer_effect_type returned 'unknown_ratio' for a well-formed binary "
        f"StudyDict. This is the P0-1 silent-corruption regression: the inference "
        f"function is reading raw RDA keys ('Experimental.cases', etc.) instead "
        f"of the StudyDict keys ('events_int', 'total_int', ...). Got: {per_study!r}"
    )
    assert per_study in {"OR", "RR"}

    # Outcome-level majority vote.
    infer_outcome_types(outcome)
    inferred = outcome["inferred_effect_type"]
    assert inferred != "unknown_ratio", (
        f"infer_outcome_types set inferred_effect_type to 'unknown_ratio' for a "
        f"binary outcome with full event/N data. P0-1 regression. Got: {inferred!r}"
    )
    assert inferred in {"OR", "RR"}

    # And the orchestrator's ratio flag must agree (binary -> log scale).
    assert _is_ratio_type(inferred) is True, (
        f"is_ratio flag must be True for ratio outcome {inferred!r}"
    )


# ---------------------------------------------------------------------------
# Continuous outcome: parse_rows -> infer_outcome_types must yield MD (or SMD)
# and the orchestrator must treat the result as a non-ratio (no log transform).
# ---------------------------------------------------------------------------

def test_continuous_outcome_classified_as_md_not_log_transformed():
    """A continuous outcome with means/SDs must be inferred as MD or SMD and
    must NOT trigger the log-transform path in the orchestrator.

    Under P0-1, the function would return "unknown_ratio", which is in
    `_RATIO_TYPES`, so the orchestrator would log-transform mean differences
    before pooling -- the silent corruption documented in the review.
    """
    md = 12.3 - 14.8  # = -2.5
    rows = [
        {
            "Study": "Lee 2010", "Study.year": 2010,
            "Analysis.name": "Six-minute walk distance",
            "Mean": md, "CI.start": -5.1, "CI.end": 0.1,
            "Experimental.cases": None, "Experimental.N": 50,
            "Control.cases": None, "Control.N": 50,
            "Experimental.mean": 12.3, "Experimental.SD": 4.1,
            "Control.mean": 14.8, "Control.SD": 3.9,
        },
        {
            "Study": "Park 2012", "Study.year": 2012,
            "Analysis.name": "Six-minute walk distance",
            "Mean": md, "CI.start": -4.6, "CI.end": -0.4,
            "Experimental.cases": None, "Experimental.N": 60,
            "Control.cases": None, "Control.N": 60,
            "Experimental.mean": 12.3, "Experimental.SD": 4.0,
            "Control.mean": 14.8, "Control.SD": 4.0,
        },
    ]

    review = parse_rows("CD000002", rows, min_year=None)
    outcome = review["outcomes"][0]
    assert outcome["data_type"] == "continuous"

    study = outcome["studies"][0]
    # Sanity: StudyDict uses renamed keys.
    assert study["mean_int"] == 12.3
    assert study["sd_int"] == 4.1
    assert study["n_int"] == 50
    assert "Experimental.mean" not in study

    per_study = infer_effect_type(study)
    assert per_study != "unknown_ratio", (
        f"infer_effect_type returned 'unknown_ratio' for a well-formed continuous "
        f"StudyDict. P0-1 regression: function is reading 'Experimental.mean' / "
        f"'Experimental.SD' / 'Experimental.N' instead of 'mean_int' / 'sd_int' / "
        f"'n_int'. Got: {per_study!r}"
    )
    assert per_study in {"MD", "SMD"}

    infer_outcome_types(outcome)
    inferred = outcome["inferred_effect_type"]
    assert inferred in {"MD", "SMD"}, (
        f"Continuous outcome must be inferred as MD or SMD; got {inferred!r}. "
        f"If 'unknown_ratio', this is the P0-1 silent log-transform bug."
    )

    # Critical: MD must NOT be treated as a ratio (would log-transform a
    # potentially-negative mean difference, which silently corrupts pooling).
    assert _is_ratio_type(inferred) is False, (
        f"is_ratio flag must be False for difference outcome {inferred!r}; "
        f"otherwise the orchestrator log-transforms mean differences."
    )
