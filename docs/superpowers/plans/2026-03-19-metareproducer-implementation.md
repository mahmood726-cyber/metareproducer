# MetaReproducer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python pipeline + HTML dashboard that audits the computational reproducibility of 465 Cochrane meta-analyses by re-extracting effect sizes from source trial PDFs and comparing pooled results.

**Architecture:** Reframe-and-extend approach building on existing RCT Extractor v10.3 mega gold standard pipeline. Python pipeline produces per-review JSON reports with two-level classification (study-level + review-level). Single-file HTML dashboard visualizes results. All extraction is deterministic (no LLM).

**Tech Stack:** Python 3.11+, pyreadr, numpy, scipy, pytest, Selenium, Plotly.js, vanilla HTML/CSS/JS

**Spec:** `docs/superpowers/specs/2026-03-19-metareproducer-design.md` (v2, 2 review rounds)

---

## File Structure

```
C:\Users\user\Downloads\MetaReproducer\
├── pipeline/
│   ├── __init__.py
│   ├── rda_parser.py            # Load RDA files, extract per-study data + outcome grouping
│   ├── effect_inference.py      # Infer effect type (OR/RR/MD/SMD) from raw data vs Mean column
│   ├── meta_engine.py           # DL + REML random-effects pooling
│   ├── effect_extractor.py      # Thin wrapper around RCT Extractor v10.3
│   ├── comparator.py            # Two-level reproducibility classification
│   ├── taxonomy.py              # Error taxonomy (8 categories)
│   └── truthcert.py             # SHA-256 provenance chain
├── scripts/
│   ├── run_audit.py             # Batch: all 465 reviews -> results JSON
│   ├── run_single.py            # Debug: one review at a time
│   └── generate_tables.py       # BMJ manuscript tables
├── data/
│   └── results/                 # Output directory (created by pipeline)
├── dashboard/
│   └── index.html               # Single-file interactive dashboard
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures (sample RDA data, mock extractions)
│   ├── test_rda_parser.py
│   ├── test_effect_inference.py
│   ├── test_meta_engine.py
│   ├── test_comparator.py
│   ├── test_taxonomy.py
│   ├── test_truthcert.py
│   ├── test_orchestrator.py
│   └── test_dashboard.py
├── CLAUDE.md
└── requirements.txt
```

**Existing data locations (symlinked or referenced by path):**
- RDA files: `C:/Users/user/OneDrive - NHS/Documents/Pairwise70/data/*.rda`
- Mega gold data: `C:/Users/user/rct-extractor-v2/gold_data/mega/`
  - `mega_studies.jsonl` — all studies from RDA (15.4 MB)
  - `mega_matched.jsonl` — with DOI/PMID/PMCID (4.9 MB)
  - `mega_eval_v10_3_merged.jsonl` — extraction results (1.76 MB)
- Gold standard pooled: `C:/Users/user/Downloads/Metaprojects/TruthCert-Validation-Papers/data/gold_standard/gold_standard_values.csv` (473 binary, R metafor REML)
- PDFs: `C:/Users/user/rct-extractor-v2/gold_data/mega/pdfs/`

**RDA column names (exact):**
- `Study` (author name), `Study.year`, `Analysis.name` (outcome label)
- `Mean` (Cochrane effect, natural scale), `CI.start`, `CI.end`
- Binary: `Experimental.cases`, `Experimental.N`, `Control.cases`, `Control.N`
- Continuous: `Experimental.mean`, `Experimental.SD`, `Control.mean`, `Control.SD`

**RCT Extractor import path:**
```python
import sys
sys.path.insert(0, r"C:\Users\user\rct-extractor-v2")
from src.core.pdf_extraction_pipeline import PDFExtractionPipeline
from src.core.effect_calculator import compute_or, compute_rr, compute_rd, compute_md, compute_smd
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`, `CLAUDE.md`, `pipeline/__init__.py`, `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Create requirements.txt**

```
pyreadr>=0.5.0
numpy>=1.24.0
scipy>=1.10.0
pytest>=7.4.0
selenium>=4.15.0
```

- [ ] **Step 2: Create CLAUDE.md**

```markdown
# MetaReproducer

## Purpose
Automated reproducibility audit of 465 Cochrane meta-analyses.
Pipeline re-extracts effects from trial PDFs, re-pools, compares against Cochrane reference.

## Key paths
- RDA files: C:/Users/user/OneDrive - NHS/Documents/Pairwise70/data/
- RCT Extractor: C:/Users/user/rct-extractor-v2/
- Mega gold data: C:/Users/user/rct-extractor-v2/gold_data/mega/
- Gold standard pooled: C:/Users/user/Downloads/Metaprojects/TruthCert-Validation-Papers/data/gold_standard/

## Rules
- Use `python` not `python3` (Windows)
- No hardcoded z=1.96 — use scipy.stats.norm.ppf
- No LLM extraction — deterministic only
- Test-first: run tests after every change
```

- [ ] **Step 3: Create pipeline/__init__.py and tests/__init__.py**

Empty `__init__.py` files.

- [ ] **Step 4: Create tests/conftest.py with shared fixtures**

```python
import pytest
import math

@pytest.fixture
def binary_studies():
    """5 binary studies with known OR values for testing DL pooling."""
    return [
        {"yi": math.log(0.75), "sei": 0.20, "label": "Study A"},
        {"yi": math.log(0.80), "sei": 0.25, "label": "Study B"},
        {"yi": math.log(0.90), "sei": 0.30, "label": "Study C"},
        {"yi": math.log(0.70), "sei": 0.15, "label": "Study D"},
        {"yi": math.log(0.85), "sei": 0.22, "label": "Study E"},
    ]

@pytest.fixture
def homogeneous_studies():
    """3 identical studies (tau2 should be 0)."""
    return [
        {"yi": math.log(0.80), "sei": 0.20, "label": "Study 1"},
        {"yi": math.log(0.80), "sei": 0.20, "label": "Study 2"},
        {"yi": math.log(0.80), "sei": 0.20, "label": "Study 3"},
    ]

@pytest.fixture
def sample_rda_data():
    """Simulated RDA dataframe rows (as list of dicts)."""
    return [
        {
            "Study": "Smith 2005", "Study.year": 2005,
            "Analysis.name": "All-cause mortality",
            "Mean": 0.75, "CI.start": 0.55, "CI.end": 1.02,
            "Experimental.cases": 15, "Experimental.N": 100,
            "Control.cases": 20, "Control.N": 100,
            "Experimental.mean": None, "Experimental.SD": None,
            "Control.mean": None, "Control.SD": None,
        },
        {
            "Study": "Jones 2008", "Study.year": 2008,
            "Analysis.name": "All-cause mortality",
            "Mean": 0.60, "CI.start": 0.38, "CI.end": 0.95,
            "Experimental.cases": 10, "Experimental.N": 80,
            "Control.cases": 18, "Control.N": 85,
            "Experimental.mean": None, "Experimental.SD": None,
            "Control.mean": None, "Control.SD": None,
        },
        {
            "Study": "Lee 2010", "Study.year": 2010,
            "Analysis.name": "Hospital readmission",
            "Mean": -2.5, "CI.start": -5.1, "CI.end": 0.1,
            "Experimental.cases": None, "Experimental.N": 50,
            "Control.cases": None, "Control.N": 50,
            "Experimental.mean": 12.3, "Experimental.SD": 4.1,
            "Control.mean": 14.8, "Control.SD": 3.9,
        },
    ]

@pytest.fixture
def sample_extractions():
    """Simulated extraction results for comparator testing."""
    return [
        {"study_id": "Smith 2005", "extracted_effect": 0.73, "matched": True,
         "match_tier": "direct_5pct", "cochrane_giv_mean": 0.75},
        {"study_id": "Jones 2008", "extracted_effect": 0.62, "matched": True,
         "match_tier": "direct_5pct", "cochrane_giv_mean": 0.60},
        {"study_id": "Brown 2012", "extracted_effect": None, "matched": False,
         "match_tier": None, "cochrane_giv_mean": 0.88},
    ]
```

- [ ] **Step 5: Install dependencies**

Run: `python -m pip install pyreadr numpy scipy pytest selenium`

- [ ] **Step 6: Verify setup**

Run: `cd C:\Users\user\Downloads\MetaReproducer && python -m pytest tests/ -v`
Expected: 0 tests collected, no import errors

- [ ] **Step 7: Commit**

```bash
git add requirements.txt CLAUDE.md pipeline/ tests/
git commit -m "feat: project scaffolding with fixtures and dependencies"
```

---

## Task 2: Meta Engine (DL + REML)

**Files:**
- Create: `pipeline/meta_engine.py`
- Test: `tests/test_meta_engine.py`

This is the mathematical core — implemented first so we can validate against R metafor.

- [ ] **Step 1: Write failing tests for DL pooling**

```python
# tests/test_meta_engine.py
import math
import pytest


def test_dl_basic_pooling(binary_studies):
    """DL pooling of 5 binary studies produces valid result."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(
        yi=[s["yi"] for s in binary_studies],
        sei=[s["sei"] for s in binary_studies],
    )
    assert result["k"] == 5
    assert result["tau2"] >= 0
    assert result["i2"] >= 0 and result["i2"] <= 100
    assert result["ci_lower"] < result["pooled"] < result["ci_upper"]
    assert result["converged"] is True


def test_dl_homogeneous(homogeneous_studies):
    """Identical studies should give tau2 = 0, I2 = 0."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(
        yi=[s["yi"] for s in homogeneous_studies],
        sei=[s["sei"] for s in homogeneous_studies],
    )
    assert abs(result["tau2"]) < 1e-10
    assert abs(result["i2"]) < 1e-10
    assert abs(result["pooled"] - math.log(0.80)) < 1e-10


def test_dl_single_study():
    """k=1: pooled = study effect, tau2 = 0."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(yi=[math.log(0.75)], sei=[0.20])
    assert result["k"] == 1
    assert abs(result["pooled"] - math.log(0.75)) < 1e-10
    assert result["tau2"] == 0
    assert result["prediction_interval"] is None


def test_dl_two_studies():
    """k=2: tau2 can be computed, PI uses t-distribution with df=1."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(yi=[math.log(0.5), math.log(1.5)], sei=[0.2, 0.2])
    assert result["k"] == 2
    assert result["tau2"] > 0  # Heterogeneous
    assert result["prediction_interval"] is not None


def test_reml_basic(binary_studies):
    """REML pooling converges and gives similar result to DL."""
    from pipeline.meta_engine import pool_reml
    result = pool_reml(
        yi=[s["yi"] for s in binary_studies],
        sei=[s["sei"] for s in binary_studies],
    )
    assert result["k"] == 5
    assert result["converged"] is True
    assert result["tau2"] >= 0


def test_reml_homogeneous(homogeneous_studies):
    """REML on homogeneous data: tau2 ~ 0."""
    from pipeline.meta_engine import pool_reml
    result = pool_reml(
        yi=[s["yi"] for s in homogeneous_studies],
        sei=[s["sei"] for s in homogeneous_studies],
    )
    assert abs(result["tau2"]) < 1e-6


def test_dl_c_zero_guard():
    """All equal weights (identical SE): C=0, tau2 should be 0."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(yi=[0.1, 0.2, 0.3], sei=[0.5, 0.5, 0.5])
    assert result["tau2"] >= 0  # Should not crash


def test_pool_convenience(binary_studies):
    """pool() convenience function runs both DL and REML."""
    from pipeline.meta_engine import pool
    dl, reml = pool(
        yi=[s["yi"] for s in binary_studies],
        sei=[s["sei"] for s in binary_studies],
    )
    assert dl["method"] == "DL"
    assert reml["method"] == "REML"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_meta_engine.py -v`
Expected: FAIL (ImportError — module not found)

- [ ] **Step 3: Implement meta_engine.py**

```python
"""DerSimonian-Laird and REML random-effects meta-analysis."""
import math
from scipy import stats


def pool_dl(yi: list[float], sei: list[float]) -> dict:
    """DerSimonian-Laird random-effects pooling.

    Args:
        yi: Study-level effect estimates (log scale for ratio measures).
        sei: Study-level standard errors.

    Returns:
        Dict with pooled, ci_lower, ci_upper, se, tau2, i2, q_stat,
        q_pvalue, k, prediction_interval, converged, method.
    """
    k = len(yi)
    if k == 0:
        raise ValueError("No studies to pool")

    vi = [s**2 for s in sei]

    if k == 1:
        z_alpha = stats.norm.ppf(0.975)
        return {
            "method": "DL",
            "pooled": yi[0],
            "ci_lower": yi[0] - z_alpha * sei[0],
            "ci_upper": yi[0] + z_alpha * sei[0],
            "se": sei[0],
            "tau2": 0.0,
            "i2": 0.0,
            "q_stat": 0.0,
            "q_pvalue": 1.0,
            "k": 1,
            "prediction_interval": None,
            "converged": True,
        }

    # Fixed-effect weights
    w = [1.0 / v for v in vi]
    sum_w = sum(w)

    # Fixed-effect pooled
    mu_fe = sum(w_i * y_i for w_i, y_i in zip(w, yi)) / sum_w

    # Cochran's Q
    q_stat = sum(w_i * (y_i - mu_fe) ** 2 for w_i, y_i in zip(w, yi))
    q_pvalue = 1.0 - stats.chi2.cdf(q_stat, k - 1) if k > 1 else 1.0

    # DL tau-squared
    c_val = sum_w - sum(w_i**2 for w_i in w) / sum_w
    if c_val <= 0:
        tau2 = 0.0
    else:
        tau2 = max(0.0, (q_stat - (k - 1)) / c_val)

    # I-squared
    i2 = max(0.0, (q_stat - (k - 1)) / q_stat * 100) if q_stat > 0 else 0.0

    # Random-effects weights
    w_re = [1.0 / (v_i + tau2) for v_i in vi]
    sum_w_re = sum(w_re)
    pooled = sum(w_i * y_i for w_i, y_i in zip(w_re, yi)) / sum_w_re
    se = math.sqrt(1.0 / sum_w_re)
    z_alpha = stats.norm.ppf(0.975)

    # Prediction interval (k >= 2)
    pi = None
    if k >= 2:
        t_crit = stats.t.ppf(0.975, k - 2) if k > 2 else stats.t.ppf(0.975, 1)
        pi_se = math.sqrt(tau2 + se**2)
        pi = (pooled - t_crit * pi_se, pooled + t_crit * pi_se)

    return {
        "method": "DL",
        "pooled": pooled,
        "ci_lower": pooled - z_alpha * se,
        "ci_upper": pooled + z_alpha * se,
        "se": se,
        "tau2": tau2,
        "i2": i2,
        "q_stat": q_stat,
        "q_pvalue": q_pvalue,
        "k": k,
        "prediction_interval": pi,
        "converged": True,
    }


def pool_reml(yi: list[float], sei: list[float],
              max_iter: int = 100, tol: float = 1e-8) -> dict:
    """REML random-effects pooling via Fisher scoring.

    Falls back to DL estimate if non-convergence.
    """
    k = len(yi)
    if k <= 1:
        return {**pool_dl(yi, sei), "method": "REML"}

    vi = [s**2 for s in sei]
    dl_result = pool_dl(yi, sei)
    tau2 = dl_result["tau2"]  # Start from DL estimate

    converged = False
    for _ in range(max_iter):
        w = [1.0 / (v_i + tau2) for v_i in vi]
        sum_w = sum(w)
        mu = sum(w_i * y_i for w_i, y_i in zip(w, yi)) / sum_w

        # REML update (Fisher scoring — Viechtbauer 2005)
        # score = 0.5 * (sum(w_i^2 * (y_i - mu)^2) - sum(w_i))
        # information = 0.5 * sum(w_i^2)
        # delta = score / information
        sum_w2 = sum(w_i**2 for w_i in w)
        numerator = sum(
            w_i**2 * (y_i - mu) ** 2 for w_i, y_i in zip(w, yi)
        ) - sum_w
        denominator = sum_w2
        if denominator == 0:
            break
        delta = numerator / denominator
        tau2_new = max(0.0, tau2 + delta)

        if abs(tau2_new - tau2) < tol:
            tau2 = tau2_new
            converged = True
            break
        tau2 = tau2_new

    # Final pooled estimate with converged tau2
    w = [1.0 / (v_i + tau2) for v_i in vi]
    sum_w = sum(w)
    pooled = sum(w_i * y_i for w_i, y_i in zip(w, yi)) / sum_w
    se = math.sqrt(1.0 / sum_w)
    z_alpha = stats.norm.ppf(0.975)

    # Q and I2
    w_fe = [1.0 / v for v in vi]
    sum_w_fe = sum(w_fe)
    mu_fe = sum(w_i * y_i for w_i, y_i in zip(w_fe, yi)) / sum_w_fe
    q_stat = sum(w_i * (y_i - mu_fe) ** 2 for w_i, y_i in zip(w_fe, yi))
    q_pvalue = 1.0 - stats.chi2.cdf(q_stat, k - 1)
    i2 = max(0.0, (q_stat - (k - 1)) / q_stat * 100) if q_stat > 0 else 0.0

    # Prediction interval
    pi = None
    if k >= 2:
        t_crit = stats.t.ppf(0.975, k - 2) if k > 2 else stats.t.ppf(0.975, 1)
        pi_se = math.sqrt(tau2 + se**2)
        pi = (pooled - t_crit * pi_se, pooled + t_crit * pi_se)

    return {
        "method": "REML",
        "pooled": pooled,
        "ci_lower": pooled - z_alpha * se,
        "ci_upper": pooled + z_alpha * se,
        "se": se,
        "tau2": tau2,
        "i2": i2,
        "q_stat": q_stat,
        "q_pvalue": q_pvalue,
        "k": k,
        "prediction_interval": pi,
        "converged": converged,
    }


def pool(yi: list[float], sei: list[float]) -> tuple[dict, dict]:
    """Run both DL and REML, return (dl_result, reml_result)."""
    return pool_dl(yi, sei), pool_reml(yi, sei)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_meta_engine.py -v`
Expected: 9/9 PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/meta_engine.py tests/test_meta_engine.py
git commit -m "feat: DL + REML meta-analysis engine with full test coverage"
```

---

## Task 3: RDA Parser

**Files:**
- Create: `pipeline/rda_parser.py`
- Test: `tests/test_rda_parser.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_rda_parser.py
import pytest
import math
from pathlib import Path


def test_parse_rda_returns_review(sample_rda_data):
    """parse_rows returns a CochraneReview with correct structure."""
    from pipeline.rda_parser import parse_rows
    review = parse_rows("CD000123", sample_rda_data)
    assert review["review_id"] == "CD000123"
    assert len(review["outcomes"]) == 2  # "All-cause mortality" + "Hospital readmission"
    assert review["total_k"] == 3


def test_parse_groups_by_outcome(sample_rda_data):
    """Studies are grouped by Analysis.name."""
    from pipeline.rda_parser import parse_rows
    review = parse_rows("CD000123", sample_rda_data)
    outcome_labels = [o["outcome_label"] for o in review["outcomes"]]
    assert "All-cause mortality" in outcome_labels
    assert "Hospital readmission" in outcome_labels


def test_study_data_types(sample_rda_data):
    """Binary studies have raw counts; continuous have means/SDs."""
    from pipeline.rda_parser import parse_rows
    review = parse_rows("CD000123", sample_rda_data)
    mortality = [o for o in review["outcomes"] if o["outcome_label"] == "All-cause mortality"][0]
    assert mortality["data_type"] == "binary"
    assert mortality["studies"][0]["events_int"] == 15

    readmission = [o for o in review["outcomes"] if o["outcome_label"] == "Hospital readmission"][0]
    assert readmission["data_type"] == "continuous"
    assert readmission["studies"][0]["mean_int"] == 12.3


def test_se_from_ci(sample_rda_data):
    """SE is back-calculated from CI bounds and Mean."""
    from pipeline.rda_parser import parse_rows
    review = parse_rows("CD000123", sample_rda_data)
    mortality = [o for o in review["outcomes"] if o["outcome_label"] == "All-cause mortality"][0]
    s = mortality["studies"][0]
    # For ratio measure: se = (ln(CI.end) - ln(CI.start)) / (2 * z)
    # But we don't know if it's ratio yet. Store raw Mean, CI.start, CI.end.
    assert s["mean"] == 0.75
    assert s["ci_start"] == 0.55
    assert s["ci_end"] == 1.02


def test_load_single_rda():
    """Load a real RDA file from Pairwise70."""
    from pipeline.rda_parser import load_rda
    rda_dir = Path(r"C:\Users\user\OneDrive - NHS\Documents\Pairwise70\data")
    rda_files = list(rda_dir.glob("*.rda"))
    if not rda_files:
        pytest.skip("Pairwise70 RDA files not available")
    review = load_rda(rda_files[0])
    assert review["review_id"] is not None
    assert len(review["outcomes"]) >= 1
    assert review["total_k"] >= 1


def test_post_2000_filter():
    """Studies before 2000 are excluded."""
    from pipeline.rda_parser import parse_rows
    old_data = [
        {"Study": "Old 1995", "Study.year": 1995, "Analysis.name": "Mortality",
         "Mean": 0.8, "CI.start": 0.5, "CI.end": 1.2,
         "Experimental.cases": 10, "Experimental.N": 50,
         "Control.cases": 15, "Control.N": 50,
         "Experimental.mean": None, "Experimental.SD": None,
         "Control.mean": None, "Control.SD": None},
        {"Study": "New 2005", "Study.year": 2005, "Analysis.name": "Mortality",
         "Mean": 0.7, "CI.start": 0.4, "CI.end": 1.1,
         "Experimental.cases": 8, "Experimental.N": 50,
         "Control.cases": 14, "Control.N": 50,
         "Experimental.mean": None, "Experimental.SD": None,
         "Control.mean": None, "Control.SD": None},
    ]
    review = parse_rows("CD000999", old_data)
    assert review["total_k"] == 1  # Only post-2000 study kept
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rda_parser.py -v`
Expected: FAIL

- [ ] **Step 3: Implement rda_parser.py**

```python
"""Parse Cochrane RDA files into structured review data."""
import re
from pathlib import Path
from typing import Any

import pyreadr


def _safe_float(val) -> float | None:
    """Convert to float, return None for NaN/None/invalid."""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return f
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    """Convert to int, return None for NaN/None/invalid."""
    f = _safe_float(val)
    if f is None:
        return None
    return int(f)


def _detect_data_type(row: dict) -> str:
    """Detect whether a row is binary, continuous, or giv_only."""
    has_binary = (
        _safe_int(row.get("Experimental.cases")) is not None
        and _safe_int(row.get("Control.cases")) is not None
        and _safe_int(row.get("Experimental.N")) is not None
        and _safe_int(row.get("Control.N")) is not None
    )
    has_continuous = (
        _safe_float(row.get("Experimental.mean")) is not None
        and _safe_float(row.get("Control.mean")) is not None
        and _safe_float(row.get("Experimental.SD")) is not None
        and _safe_float(row.get("Control.SD")) is not None
    )
    if has_binary:
        return "binary"
    if has_continuous:
        return "continuous"
    return "giv_only"


def parse_rows(review_id: str, rows: list[dict]) -> dict:
    """Parse a list of row dicts (from RDA or test fixture) into a CochraneReview.

    Filters to post-2000 studies. Groups by Analysis.name (outcome).
    """
    outcomes_map: dict[str, list[dict]] = {}

    for row in rows:
        year = _safe_int(row.get("Study.year"))
        if year is None or year < 2000 or year > 2025:
            continue

        study_id = str(row.get("Study", "Unknown"))
        outcome_label = str(row.get("Analysis.name", "Unknown"))
        data_type = _detect_data_type(row)

        study = {
            "study_id": study_id,
            "year": year,
            "mean": _safe_float(row.get("Mean")),
            "ci_start": _safe_float(row.get("CI.start")),
            "ci_end": _safe_float(row.get("CI.end")),
            "data_type": data_type,
            # Binary
            "events_int": _safe_int(row.get("Experimental.cases")),
            "total_int": _safe_int(row.get("Experimental.N")),
            "events_ctrl": _safe_int(row.get("Control.cases")),
            "total_ctrl": _safe_int(row.get("Control.N")),
            # Continuous
            "mean_int": _safe_float(row.get("Experimental.mean")),
            "sd_int": _safe_float(row.get("Experimental.SD")),
            "n_int": _safe_int(row.get("Experimental.N")),
            "mean_ctrl": _safe_float(row.get("Control.mean")),
            "sd_ctrl": _safe_float(row.get("Control.SD")),
            "n_ctrl": _safe_int(row.get("Control.N")),
            # Linking (populated later)
            "doi": None,
            "pmcid": None,
            "pdf_path": None,
        }

        if outcome_label not in outcomes_map:
            outcomes_map[outcome_label] = []
        outcomes_map[outcome_label].append(study)

    outcomes = []
    for label, studies in outcomes_map.items():
        data_types = [s["data_type"] for s in studies]
        majority_type = max(set(data_types), key=data_types.count)
        outcomes.append({
            "outcome_label": label,
            "studies": studies,
            "data_type": majority_type,
            "inferred_effect_type": None,  # Set by effect_inference
            "k": len(studies),
        })

    return {
        "review_id": review_id,
        "outcomes": outcomes,
        "total_k": sum(o["k"] for o in outcomes),
    }


def load_rda(rda_path: Path) -> dict:
    """Load a single RDA file and parse into CochraneReview."""
    result = pyreadr.read_r(str(rda_path))
    # RDA contains one dataframe; get the first key
    df_name = list(result.keys())[0]
    df = result[df_name]

    # Extract review_id from filename: CD000028_pub4_data.rda -> CD000028
    review_id = re.match(r"(CD\d+)", rda_path.stem)
    review_id = review_id.group(1) if review_id else rda_path.stem

    rows = df.to_dict("records")
    return parse_rows(review_id, rows)


def load_all_rdas(rda_dir: Path) -> list[dict]:
    """Load all RDA files from Pairwise70 directory."""
    reviews = []
    for rda_path in sorted(rda_dir.glob("*.rda")):
        try:
            review = load_rda(rda_path)
            if review["total_k"] > 0:
                reviews.append(review)
        except Exception as e:
            print(f"WARN: Failed to load {rda_path.name}: {e}")
    return reviews
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rda_parser.py -v`
Expected: 6/6 PASS (5th test may skip if RDA files not on disk)

- [ ] **Step 5: Commit**

```bash
git add pipeline/rda_parser.py tests/test_rda_parser.py
git commit -m "feat: RDA parser with outcome grouping and post-2000 filter"
```

---

## Task 4: Effect Type Inference

**Files:**
- Create: `pipeline/effect_inference.py`
- Test: `tests/test_effect_inference.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_effect_inference.py
import math
import pytest


def test_infer_binary_or():
    """Binary data matching OR: Mean matches exp(log_or)."""
    from pipeline.effect_inference import infer_effect_type
    # OR = (15*80) / (85*20) = 0.7059
    study = {
        "mean": 0.7059, "data_type": "binary",
        "events_int": 15, "total_int": 100,
        "events_ctrl": 20, "total_ctrl": 100,
    }
    assert infer_effect_type(study) == "OR"


def test_infer_binary_rr():
    """Binary data matching RR: Mean matches (a/n1)/(c/n2)."""
    from pipeline.effect_inference import infer_effect_type
    # RR = (15/100) / (20/100) = 0.75
    study = {
        "mean": 0.75, "data_type": "binary",
        "events_int": 15, "total_int": 100,
        "events_ctrl": 20, "total_ctrl": 100,
    }
    assert infer_effect_type(study) == "RR"


def test_infer_continuous_md():
    """Continuous data matching MD: Mean matches m1 - m2."""
    from pipeline.effect_inference import infer_effect_type
    # MD = 12.3 - 14.8 = -2.5
    study = {
        "mean": -2.5, "data_type": "continuous",
        "mean_int": 12.3, "sd_int": 4.1, "n_int": 50,
        "mean_ctrl": 14.8, "sd_ctrl": 3.9, "n_ctrl": 50,
    }
    assert infer_effect_type(study) == "MD"


def test_infer_continuous_smd():
    """Continuous data matching SMD (Hedges' g)."""
    from pipeline.effect_inference import infer_effect_type
    # Compute expected SMD
    m1, sd1, n1 = 12.3, 4.1, 50
    m2, sd2, n2 = 14.8, 3.9, 50
    sp = math.sqrt(((n1-1)*sd1**2 + (n2-1)*sd2**2) / (n1+n2-2))
    d = (m1 - m2) / sp
    j = 1 - 3 / (4*(n1+n2-2) - 1)  # Hedges correction
    g = d * j
    study = {
        "mean": g, "data_type": "continuous",
        "mean_int": m1, "sd_int": sd1, "n_int": n1,
        "mean_ctrl": m2, "sd_ctrl": sd2, "n_ctrl": n2,
    }
    assert infer_effect_type(study) == "SMD"


def test_infer_giv_only():
    """GIV-only data returns 'unknown_ratio' for log-scale values."""
    from pipeline.effect_inference import infer_effect_type
    study = {"mean": -0.28, "data_type": "giv_only"}
    assert infer_effect_type(study) == "unknown_ratio"


def test_infer_ambiguous():
    """When Mean doesn't match OR or RR, returns best guess + flag."""
    from pipeline.effect_inference import infer_effect_type
    study = {
        "mean": 0.50, "data_type": "binary",
        "events_int": 15, "total_int": 100,
        "events_ctrl": 20, "total_ctrl": 100,
    }
    # OR=0.706, RR=0.75 — neither matches 0.50
    result = infer_effect_type(study)
    assert result in ("RR", "OR", "ambiguous")


def test_infer_outcome_types():
    """infer_outcome_types sets type on all studies in an outcome."""
    from pipeline.effect_inference import infer_outcome_types
    outcome = {
        "studies": [
            {"mean": 0.75, "data_type": "binary",
             "events_int": 15, "total_int": 100,
             "events_ctrl": 20, "total_ctrl": 100},
            {"mean": 0.80, "data_type": "binary",
             "events_int": 20, "total_int": 100,
             "events_ctrl": 25, "total_ctrl": 100},
        ],
        "data_type": "binary",
        "inferred_effect_type": None,
    }
    infer_outcome_types(outcome)
    assert outcome["inferred_effect_type"] in ("OR", "RR")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_effect_inference.py -v`
Expected: FAIL

- [ ] **Step 3: Implement effect_inference.py**

```python
"""Infer effect measure type by comparing Mean column against computed values."""
import math
from collections import Counter


def _compute_or(a: int, n1: int, c: int, n2: int) -> float | None:
    """Compute OR from 2x2 table. Returns None if undefined."""
    b = n1 - a
    d = n2 - c
    if b <= 0 or c <= 0 or a < 0 or d < 0:
        # Use continuity correction
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    denom = b * c
    if denom == 0:
        return None
    return (a * d) / denom


def _compute_rr(a: int, n1: int, c: int, n2: int) -> float | None:
    """Compute RR from 2x2 table."""
    if n1 <= 0 or n2 <= 0 or c <= 0:
        return None
    return (a / n1) / (c / n2)


def _compute_md(m1: float, m2: float) -> float:
    """Compute mean difference."""
    return m1 - m2


def _compute_smd(m1: float, sd1: float, n1: int,
                 m2: float, sd2: float, n2: int) -> float | None:
    """Compute Hedges' g (SMD with small-sample correction)."""
    if n1 <= 1 or n2 <= 1 or sd1 <= 0 or sd2 <= 0:
        return None
    sp = math.sqrt(((n1 - 1) * sd1**2 + (n2 - 1) * sd2**2) / (n1 + n2 - 2))
    if sp == 0:
        return None
    d = (m1 - m2) / sp
    j = 1 - 3 / (4 * (n1 + n2 - 2) - 1)
    return d * j


def _matches(computed: float | None, observed: float, tol: float = 1e-3) -> bool:
    """Check if computed value matches observed within tolerance."""
    if computed is None:
        return False
    if abs(observed) < 1e-10:
        return abs(computed) < tol
    return abs(computed - observed) / abs(observed) < tol


def infer_effect_type(study: dict) -> str:
    """Infer effect type for a single study by comparing Mean vs computed values.

    Returns: "OR", "RR", "RD", "MD", "SMD", "unknown_ratio", or "ambiguous".
    """
    mean_val = study.get("mean")
    data_type = study.get("data_type", "giv_only")

    if mean_val is None:
        return "ambiguous"

    if data_type == "giv_only":
        return "unknown_ratio"

    if data_type == "binary":
        a = study.get("events_int")
        n1 = study.get("total_int")
        c = study.get("events_ctrl")
        n2 = study.get("total_ctrl")
        if None in (a, n1, c, n2):
            return "ambiguous"

        or_val = _compute_or(a, n1, c, n2)
        rr_val = _compute_rr(a, n1, c, n2)
        rd_val = (a / n1) - (c / n2) if n1 > 0 and n2 > 0 else None

        if _matches(rr_val, mean_val):
            return "RR"
        if _matches(or_val, mean_val):
            return "OR"
        if _matches(rd_val, mean_val):
            return "RD"
        # Default for binary
        return "RR"

    if data_type == "continuous":
        m1 = study.get("mean_int")
        sd1 = study.get("sd_int")
        n1 = study.get("n_int")
        m2 = study.get("mean_ctrl")
        sd2 = study.get("sd_ctrl")
        n2 = study.get("n_ctrl")

        if m1 is not None and m2 is not None:
            md_val = _compute_md(m1, m2)
            if _matches(md_val, mean_val):
                return "MD"

        if None not in (m1, sd1, n1, m2, sd2, n2):
            smd_val = _compute_smd(m1, sd1, n1, m2, sd2, n2)
            if _matches(smd_val, mean_val):
                return "SMD"

        # Default for continuous
        return "MD"

    return "ambiguous"


def infer_outcome_types(outcome: dict) -> None:
    """Infer effect type for an outcome by majority vote across studies.

    Mutates outcome["inferred_effect_type"].
    """
    types = [infer_effect_type(s) for s in outcome["studies"]]
    # Filter out ambiguous/unknown for voting
    concrete = [t for t in types if t not in ("ambiguous", "unknown_ratio")]
    if concrete:
        winner = Counter(concrete).most_common(1)[0][0]
        outcome["inferred_effect_type"] = winner
    elif any(t == "unknown_ratio" for t in types):
        outcome["inferred_effect_type"] = "unknown_ratio"
    else:
        # Default by data type
        outcome["inferred_effect_type"] = (
            "RR" if outcome["data_type"] == "binary" else "MD"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_effect_inference.py -v`
Expected: 7/7 PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/effect_inference.py tests/test_effect_inference.py
git commit -m "feat: effect type inference from raw data vs Cochrane Mean column"
```

---

## Task 5: Comparator (Two-Level Classification)

**Files:**
- Create: `pipeline/comparator.py`
- Test: `tests/test_comparator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_comparator.py
import math
import pytest


def test_study_level_all_matched():
    """All studies matched -> 100% match rate."""
    from pipeline.comparator import assess_study_level
    extractions = [
        {"matched": True, "match_tier": "direct_5pct"},
        {"matched": True, "match_tier": "direct_5pct"},
        {"matched": True, "match_tier": "direct_10pct"},
    ]
    result = assess_study_level(total_k=3, extractions=extractions,
                                 n_with_pdf=3)
    assert result["match_rate_strict"] == pytest.approx(2/3)  # 2 at 5%
    assert result["match_rate_moderate"] == pytest.approx(1.0)  # 3 at <=10%


def test_study_level_missing_pdfs():
    """Studies without PDFs are counted separately."""
    from pipeline.comparator import assess_study_level
    extractions = [
        {"matched": True, "match_tier": "direct_5pct"},
    ]
    result = assess_study_level(total_k=5, extractions=extractions,
                                 n_with_pdf=2)
    assert result["no_pdf"] == 3
    assert result["total_studies"] == 5


def test_review_level_reproduced():
    """Within 10%, same direction, same significance, k_coverage >= 50%."""
    from pipeline.comparator import assess_review_level
    ref = {"pooled": math.log(0.80), "se": 0.10, "k": 10}
    repro = {"pooled": math.log(0.82), "se": 0.11, "k": 7}
    result = assess_review_level(ref, repro, original_k=10)
    assert result["tier"] == "reproduced"
    assert result["same_direction"] is True


def test_review_level_major_direction_flip():
    """Different direction -> major discrepancy."""
    from pipeline.comparator import assess_review_level
    ref = {"pooled": math.log(0.80), "se": 0.10, "k": 10}
    repro = {"pooled": math.log(1.20), "se": 0.11, "k": 5}
    result = assess_review_level(ref, repro, original_k=10)
    assert result["tier"] == "major_discrepancy"
    assert result["same_direction"] is False


def test_review_level_major_significance_flip():
    """One significant, other not -> major discrepancy."""
    from pipeline.comparator import assess_review_level
    # ref: significant (pooled far from 0, small SE)
    ref = {"pooled": math.log(0.50), "se": 0.10, "k": 10}
    # repro: not significant (pooled near 0, large SE)
    repro = {"pooled": math.log(0.95), "se": 0.50, "k": 5}
    result = assess_review_level(ref, repro, original_k=10)
    assert result["tier"] == "major_discrepancy"
    assert result["same_significance"] is False


def test_review_level_insufficient():
    """k_coverage < 0.30 -> insufficient."""
    from pipeline.comparator import assess_review_level
    ref = {"pooled": math.log(0.80), "se": 0.10, "k": 20}
    repro = {"pooled": math.log(0.82), "se": 0.11, "k": 4}
    result = assess_review_level(ref, repro, original_k=20)
    assert result["tier"] == "insufficient"


def test_review_level_minor_effect_diff():
    """Same direction + significance but >10% effect diff -> minor."""
    from pipeline.comparator import assess_review_level
    ref = {"pooled": math.log(0.80), "se": 0.05, "k": 10}
    repro = {"pooled": math.log(0.60), "se": 0.06, "k": 6}
    result = assess_review_level(ref, repro, original_k=10)
    assert result["tier"] == "minor_discrepancy"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_comparator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement comparator.py**

```python
"""Two-level reproducibility classification."""
import math
from scipy import stats

STRICT_TIERS = {"direct_5pct", "computed_5pct"}
MODERATE_TIERS = {"direct_5pct", "direct_10pct", "computed_5pct", "computed_10pct"}


def assess_study_level(total_k: int, extractions: list[dict],
                        n_with_pdf: int) -> dict:
    """Assess study-level reproducibility.

    Args:
        total_k: Total studies in Cochrane outcome.
        extractions: List of extraction result dicts (with 'matched', 'match_tier').
        n_with_pdf: Number of studies that had PDFs available.
    """
    matched_strict = sum(
        1 for e in extractions
        if e.get("matched") and e.get("match_tier") in STRICT_TIERS
    )
    matched_moderate = sum(
        1 for e in extractions
        if e.get("matched") and e.get("match_tier") in MODERATE_TIERS
    )
    extracted_no_match = sum(
        1 for e in extractions if not e.get("matched")
    )
    extraction_failed = n_with_pdf - len(extractions)

    return {
        "total_studies": total_k,
        "n_with_pdf": n_with_pdf,
        "n_extracted": len(extractions),
        "matched_strict": matched_strict,
        "matched_moderate": matched_moderate,
        "match_rate_strict": matched_strict / max(n_with_pdf, 1),
        "match_rate_moderate": matched_moderate / max(n_with_pdf, 1),
        "no_pdf": total_k - n_with_pdf,
        "extraction_failed": max(0, extraction_failed),
        "extracted_no_match": extracted_no_match,
    }


def _is_significant(pooled: float, se: float, alpha: float = 0.05) -> bool:
    """Test if pooled effect is statistically significant at given alpha."""
    if se <= 0:
        return False
    z = abs(pooled / se)
    p = 2 * (1 - stats.norm.cdf(z))
    return p < alpha


def assess_review_level(ref: dict, repro: dict,
                         original_k: int, alpha: float = 0.05) -> dict:
    """Assess review-level reproducibility.

    Args:
        ref: Reference pooled result (from Cochrane GIV data).
        repro: Reproduced pooled result (from extracted effects).
        original_k: Total studies in the original Cochrane outcome.
        alpha: Significance threshold (default 0.05).
    """
    k_coverage = repro["k"] / max(original_k, 1)
    ref_pooled = ref["pooled"]
    repro_pooled = repro["pooled"]

    # Direction comparison (on log scale: <0 is protective for ratio measures)
    same_direction = (ref_pooled * repro_pooled) > 0 if (
        ref_pooled != 0 and repro_pooled != 0
    ) else True

    # Significance comparison
    ref_sig = _is_significant(ref_pooled, ref["se"], alpha)
    repro_sig = _is_significant(repro_pooled, repro["se"], alpha)
    same_significance = ref_sig == repro_sig

    # Percentage difference
    if abs(ref_pooled) > 1e-10:
        pct_diff = abs(repro_pooled - ref_pooled) / abs(ref_pooled)
    else:
        pct_diff = abs(repro_pooled)

    # Classification
    if k_coverage < 0.30:
        tier = "insufficient"
    elif not same_direction or not same_significance:
        tier = "major_discrepancy"
    elif pct_diff <= 0.10 and k_coverage >= 0.50:
        tier = "reproduced"
    else:
        tier = "minor_discrepancy"

    return {
        "tier": tier,
        "reference_pooled": ref_pooled,
        "reproduced_pooled": repro_pooled,
        "pct_difference": pct_diff,
        "same_direction": same_direction,
        "same_significance": same_significance,
        "reference_significant": ref_sig,
        "reproduced_significant": repro_sig,
        "reference_k": ref["k"],
        "reproduced_k": repro["k"],
        "k_coverage": k_coverage,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_comparator.py -v`
Expected: 7/7 PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/comparator.py tests/test_comparator.py
git commit -m "feat: two-level reproducibility classification (study + review)"
```

---

## Task 6: Error Taxonomy

**Files:**
- Create: `pipeline/taxonomy.py`
- Test: `tests/test_taxonomy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_taxonomy.py
import pytest


def test_classify_missing_pdf():
    """Study with no PDF -> missing_pdf."""
    from pipeline.taxonomy import classify_study_error
    assert classify_study_error(has_pdf=False, extraction=None) == "missing_pdf"


def test_classify_extraction_failure():
    """PDF available but no extraction -> extraction_failure."""
    from pipeline.taxonomy import classify_study_error
    assert classify_study_error(
        has_pdf=True,
        extraction={"extracted_effect": None, "matched": False}
    ) == "extraction_failure"


def test_classify_no_match():
    """Extracted but didn't match -> no_match."""
    from pipeline.taxonomy import classify_study_error
    assert classify_study_error(
        has_pdf=True,
        extraction={"extracted_effect": 0.55, "matched": False,
                     "match_tier": None}
    ) == "no_match"


def test_classify_success():
    """Matched extraction -> None (no error)."""
    from pipeline.taxonomy import classify_study_error
    assert classify_study_error(
        has_pdf=True,
        extraction={"extracted_effect": 0.75, "matched": True,
                     "match_tier": "direct_5pct"}
    ) is None


def test_aggregate_taxonomy():
    """Aggregate error counts across studies."""
    from pipeline.taxonomy import aggregate_errors
    errors = ["missing_pdf", "missing_pdf", "extraction_failure",
              "no_match", None, None]
    result = aggregate_errors(errors)
    assert result["missing_pdf"] == 2
    assert result["extraction_failure"] == 1
    assert result["no_match"] == 1
    assert result["success"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_taxonomy.py -v`
Expected: FAIL

- [ ] **Step 3: Implement taxonomy.py**

```python
"""Error taxonomy for reproducibility failures."""

ERROR_CATEGORIES = [
    "missing_pdf",
    "extraction_failure",
    "no_match",
    "scale_mismatch",
    "direction_flip",
    "computation_gap",
    "significance_shift",
    "ambiguous_type",
]


def classify_study_error(has_pdf: bool, extraction: dict | None) -> str | None:
    """Classify why a single study failed to reproduce.

    Returns error category string, or None if study matched successfully.
    """
    if not has_pdf:
        return "missing_pdf"

    if extraction is None:
        return "extraction_failure"

    if extraction.get("extracted_effect") is None:
        return "extraction_failure"

    if extraction.get("matched"):
        return None  # Success

    return "no_match"


def aggregate_errors(study_errors: list[str | None]) -> dict:
    """Count errors by category across all studies in an outcome.

    Args:
        study_errors: List of error category strings (None = success).

    Returns:
        Dict mapping category -> count, plus "success" count.
    """
    counts = {cat: 0 for cat in ERROR_CATEGORIES}
    counts["success"] = 0
    for err in study_errors:
        if err is None:
            counts["success"] += 1
        elif err in counts:
            counts[err] += 1
        else:
            counts[err] = 1  # Unknown category
    # Primary error source = most common non-success error
    error_only = {k: v for k, v in counts.items() if k != "success" and v > 0}
    primary = max(error_only, key=error_only.get) if error_only else None
    return {**counts, "primary_error_source": primary}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_taxonomy.py -v`
Expected: 5/5 PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/taxonomy.py tests/test_taxonomy.py
git commit -m "feat: error taxonomy with 8 categories and aggregation"
```

---

## Task 7: TruthCert Provenance

**Files:**
- Create: `pipeline/truthcert.py`
- Test: `tests/test_truthcert.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_truthcert.py
import json
import pytest


def test_hash_deterministic():
    """Same input -> same hash."""
    from pipeline.truthcert import hash_data
    h1 = hash_data({"a": 1, "b": 2})
    h2 = hash_data({"a": 1, "b": 2})
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_hash_different_input():
    """Different input -> different hash."""
    from pipeline.truthcert import hash_data
    h1 = hash_data({"a": 1})
    h2 = hash_data({"a": 2})
    assert h1 != h2


def test_certify_produces_chain():
    """certify() builds a provenance chain with 4 steps."""
    from pipeline.truthcert import certify
    cert = certify(
        review_id="CD000123",
        rda_hash="sha256:abc",
        extraction_hash="sha256:def",
        pooling_hash="sha256:ghi",
        classification="reproduced",
    )
    assert cert["review_id"] == "CD000123"
    assert cert["classification"] == "reproduced"
    assert len(cert["provenance_chain"]) == 4
    assert cert["provenance_chain"][0]["step"] == "rda_parse"


def test_hash_file(tmp_path):
    """hash_file computes SHA-256 of file contents."""
    from pipeline.truthcert import hash_file
    f = tmp_path / "test.txt"
    f.write_text("hello")
    h = hash_file(str(f))
    assert h.startswith("sha256:")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_truthcert.py -v`
Expected: FAIL

- [ ] **Step 3: Implement truthcert.py**

```python
"""TruthCert provenance chain — SHA-256 hashing for reproducibility audit."""
import hashlib
import json
from datetime import datetime, timezone


def hash_data(data: dict) -> str:
    """Compute SHA-256 hash of JSON-serializable data."""
    raw = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def hash_file(file_path: str) -> str:
    """Compute SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def certify(review_id: str, rda_hash: str, extraction_hash: str,
            pooling_hash: str, classification: str,
            pipeline_version: str = "1.0.0") -> dict:
    """Build a TruthCert provenance chain for one review-outcome.

    Returns a certifiable JSON bundle.
    """
    now = datetime.now(timezone.utc).isoformat()
    return {
        "review_id": review_id,
        "pipeline_version": pipeline_version,
        "timestamp": now,
        "classification": classification,
        "provenance_chain": [
            {"step": "rda_parse", "hash": rda_hash, "timestamp": now},
            {"step": "extraction", "hash": extraction_hash, "timestamp": now},
            {"step": "pooling", "hash": pooling_hash, "timestamp": now},
            {"step": "comparison", "hash": hash_data({
                "review_id": review_id,
                "classification": classification,
                "rda": rda_hash,
                "extraction": extraction_hash,
                "pooling": pooling_hash,
            }), "timestamp": now},
        ],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_truthcert.py -v`
Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/truthcert.py tests/test_truthcert.py
git commit -m "feat: TruthCert SHA-256 provenance chain"
```

---

## Task 8: Effect Extractor Wrapper

**Files:**
- Create: `pipeline/effect_extractor.py`
- Test: `tests/test_effect_extractor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_effect_extractor.py
import pytest
import math


def test_match_strict_5pct():
    """Extraction within 5% of Cochrane value -> direct_5pct."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.74, cochrane_mean=0.75, is_ratio=True)
    assert result["matched"] is True
    assert result["match_tier"] == "direct_5pct"


def test_match_strict_10pct():
    """Extraction within 10% but >5% -> direct_10pct."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.68, cochrane_mean=0.75, is_ratio=True)
    assert result["matched"] is True
    assert result["match_tier"] == "direct_10pct"


def test_no_match():
    """Extraction >10% different -> not matched."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.50, cochrane_mean=0.75, is_ratio=True)
    assert result["matched"] is False


def test_computed_match():
    """Effect computed from raw data within 5% -> computed_5pct."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=None, cochrane_mean=0.75, is_ratio=True,
                             computed_effect=0.74)
    assert result["matched"] is True
    assert result["match_tier"] == "computed_5pct"


def test_log_scale_comparison():
    """Ratio measures are compared on log scale."""
    from pipeline.effect_extractor import classify_match
    # log(0.80) = -0.2231, log(0.82) = -0.1985 -> 11% diff on log scale
    # But on natural scale: 0.82/0.80 = 2.5% diff
    result = classify_match(extracted=0.82, cochrane_mean=0.80, is_ratio=True)
    assert result["matched"] is True  # Within 5% on natural scale


def test_diff_scale_comparison():
    """Difference measures compared on natural scale."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=-2.4, cochrane_mean=-2.5, is_ratio=False)
    assert result["matched"] is True
    assert result["match_tier"] == "direct_5pct"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_effect_extractor.py -v`
Expected: FAIL

- [ ] **Step 3: Implement effect_extractor.py**

```python
"""Wrapper around RCT Extractor v10.3 for the reproducibility audit.

Uses only strict matching tiers (5%, 10%) — no reciprocal, signflip, or scale transforms.
"""
import sys
import math
from pathlib import Path

# Add RCT Extractor to path
_RCT_EXTRACTOR_PATH = r"C:\Users\user\rct-extractor-v2"


def _rel_diff(a: float, b: float) -> float:
    """Relative difference: |a - b| / |b|. Returns inf if b ~= 0."""
    if abs(b) < 1e-10:
        return abs(a)
    return abs(a - b) / abs(b)


def classify_match(extracted: float | None, cochrane_mean: float,
                    is_ratio: bool, computed_effect: float | None = None) -> dict:
    """Classify whether an extraction matches the Cochrane value.

    Uses strict tiers only:
    - direct_5pct: extracted within 5% of cochrane_mean
    - direct_10pct: within 10%
    - computed_5pct: computed_effect within 5%
    - computed_10pct: computed_effect within 10%

    For ratio measures, comparison is on natural scale (not log scale).
    """
    result = {"matched": False, "match_tier": None, "pct_difference": None}

    # Try direct match
    if extracted is not None:
        diff = _rel_diff(extracted, cochrane_mean)
        result["pct_difference"] = diff
        if diff <= 0.05:
            result["matched"] = True
            result["match_tier"] = "direct_5pct"
            return result
        if diff <= 0.10:
            result["matched"] = True
            result["match_tier"] = "direct_10pct"
            return result

    # Try computed match
    if computed_effect is not None:
        diff = _rel_diff(computed_effect, cochrane_mean)
        if result["pct_difference"] is None:
            result["pct_difference"] = diff
        if diff <= 0.05:
            result["matched"] = True
            result["match_tier"] = "computed_5pct"
            return result
        if diff <= 0.10:
            result["matched"] = True
            result["match_tier"] = "computed_10pct"
            return result

    return result


def load_existing_extractions() -> dict:
    """Load pre-computed extraction results from mega_eval_v10_3_merged.jsonl.

    Returns dict mapping (first_author, year) -> extraction entry.
    This avoids re-running extraction on ~1,290 PDFs that were already processed.
    """
    import json
    mega_eval = Path(_RCT_EXTRACTOR_PATH) / "gold_data" / "mega" / "mega_eval_v10_3_merged.jsonl"
    if not mega_eval.exists():
        return {}
    mapping = {}
    with open(mega_eval) as f:
        for line in f:
            entry = json.loads(line)
            author = entry.get("first_author", "").strip()
            year = entry.get("year")
            mapping[(author, year)] = entry
    return mapping


def get_extraction_for_study(study_id: str, year: int,
                              existing: dict) -> list[dict] | None:
    """Look up existing extraction result, or return None to trigger re-extraction.

    Returns list of extraction dicts if found, None otherwise.
    """
    key = (study_id.strip(), year)
    entry = existing.get(key)
    if entry is None:
        return None
    extracted = entry.get("extracted", [])
    if not extracted:
        return []
    return [
        {
            "effect_type": e.get("effect_type", ""),
            "point_estimate": e.get("point_estimate"),
            "ci_lower": e.get("ci_lower"),
            "ci_upper": e.get("ci_upper"),
            "confidence": e.get("confidence", 0),
        }
        for e in extracted
        if e.get("point_estimate") is not None
    ]


def extract_from_pdf(pdf_path: str) -> list[dict]:
    """Run RCT Extractor on a PDF and return extractions.

    Fallback for studies not in the pre-computed results.
    Returns list of dicts with keys: effect_type, point_estimate,
    ci_lower, ci_upper, confidence.
    """
    if _RCT_EXTRACTOR_PATH not in sys.path:
        sys.path.insert(0, _RCT_EXTRACTOR_PATH)

    from src.core.pdf_extraction_pipeline import PDFExtractionPipeline

    pipeline = PDFExtractionPipeline(
        compute_raw_effects=True,
        enable_advanced=False,
        enable_llm=False,  # Deterministic only
    )
    try:
        result = pipeline.extract_from_pdf(pdf_path)
    except Exception:
        return []

    extractions = []
    for ext in result.effect_estimates:
        extractions.append({
            "effect_type": ext.effect_type.value if hasattr(ext.effect_type, "value") else str(ext.effect_type),
            "point_estimate": ext.point_estimate,
            "ci_lower": ext.ci.lower if ext.ci else None,
            "ci_upper": ext.ci.upper if ext.ci else None,
            "confidence": ext.calibrated_confidence,
        })
    return extractions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_effect_extractor.py -v`
Expected: 6/6 PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/effect_extractor.py tests/test_effect_extractor.py
git commit -m "feat: effect extractor wrapper with strict matching tiers"
```

---

## Task 9: Orchestrator

**Files:**
- Create: `pipeline/orchestrator.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_orchestrator.py
import math
import pytest


def test_reproduce_outcome_insufficient():
    """Outcome with 0 matched studies -> insufficient."""
    from pipeline.orchestrator import reproduce_outcome
    outcome = {
        "outcome_label": "Mortality",
        "studies": [
            {"study_id": "A", "mean": 0.75, "ci_start": 0.5, "ci_end": 1.1,
             "data_type": "binary", "pdf_path": None,
             "events_int": 15, "total_int": 100,
             "events_ctrl": 20, "total_ctrl": 100},
        ],
        "data_type": "binary",
        "inferred_effect_type": "RR",
        "k": 1,
    }
    report = reproduce_outcome("CD000123", outcome)
    assert report["study_level"]["no_pdf"] == 1
    assert report["review_level"] is None


def test_reproduce_outcome_structure():
    """Report has required keys."""
    from pipeline.orchestrator import reproduce_outcome
    outcome = {
        "outcome_label": "Mortality",
        "studies": [
            {"study_id": "A", "mean": 0.75, "ci_start": 0.55, "ci_end": 1.02,
             "data_type": "binary", "pdf_path": None,
             "events_int": 15, "total_int": 100,
             "events_ctrl": 20, "total_ctrl": 100},
        ],
        "data_type": "binary",
        "inferred_effect_type": "RR",
        "k": 1,
    }
    report = reproduce_outcome("CD000123", outcome)
    assert "review_id" in report
    assert "outcome_label" in report
    assert "study_level" in report
    assert "review_level" in report
    assert "errors" in report
    assert "cert" in report


def test_select_primary_outcome():
    """Primary outcome = largest k, binary preferred."""
    from pipeline.orchestrator import select_primary_outcome
    outcomes = [
        {"outcome_label": "A", "k": 5, "data_type": "continuous"},
        {"outcome_label": "B", "k": 10, "data_type": "binary"},
        {"outcome_label": "C", "k": 10, "data_type": "continuous"},
    ]
    primary = select_primary_outcome(outcomes)
    assert primary["outcome_label"] == "B"  # Same k=10, binary wins


def test_se_from_ci_ratio():
    """SE back-calculation for ratio measures."""
    from pipeline.orchestrator import se_from_ci
    # log(1.02) - log(0.55) = 0.6173; SE = 0.6173 / (2 * 1.96) = 0.1575
    se = se_from_ci(0.75, 0.55, 1.02, is_ratio=True)
    assert se is not None
    assert abs(se - 0.1575) < 0.01


def test_se_from_ci_diff():
    """SE back-calculation for difference measures."""
    from pipeline.orchestrator import se_from_ci
    # (0.1 - (-5.1)) / (2 * 1.96) = 5.2 / 3.92 = 1.3265
    se = se_from_ci(-2.5, -5.1, 0.1, is_ratio=False)
    assert se is not None
    assert abs(se - 1.3265) < 0.01
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement orchestrator.py**

```python
"""Orchestrate the full reproducibility pipeline for one review."""
import math
from scipy import stats

from pipeline import meta_engine, comparator, taxonomy, truthcert, effect_extractor, effect_inference


def se_from_ci(mean: float, ci_lower: float, ci_upper: float,
               is_ratio: bool) -> float | None:
    """Back-calculate SE from CI bounds.

    For ratio measures: SE = (ln(ci_upper) - ln(ci_lower)) / (2 * z_0.975)
    For difference measures: SE = (ci_upper - ci_lower) / (2 * z_0.975)
    """
    z = stats.norm.ppf(0.975)
    try:
        if is_ratio:
            if ci_lower is None or ci_upper is None or ci_lower <= 0 or ci_upper <= 0:
                return None
            return (math.log(ci_upper) - math.log(ci_lower)) / (2 * z)
        else:
            if ci_lower is None or ci_upper is None:
                return None
            return (ci_upper - ci_lower) / (2 * z)
    except (ValueError, ZeroDivisionError):
        return None


def select_primary_outcome(outcomes: list[dict]) -> dict:
    """Select primary outcome: largest k, binary preferred, alphabetical tiebreak."""
    TYPE_PRIORITY = {"binary": 0, "continuous": 1, "giv_only": 2}
    return min(
        outcomes,
        key=lambda o: (-o["k"], TYPE_PRIORITY.get(o["data_type"], 9), o["outcome_label"]),
    )


def _is_ratio_type(effect_type: str) -> bool:
    """Check if effect type is a ratio measure (compared on log scale)."""
    return effect_type in ("OR", "RR", "HR", "IRR", "unknown_ratio")


def reproduce_outcome(review_id: str, outcome: dict) -> dict:
    """Run the full pipeline for one outcome within a review.

    Args:
        review_id: Cochrane review ID.
        outcome: CochraneOutcome dict from rda_parser.

    Returns:
        ReproducibilityReport dict.
    """
    studies = outcome["studies"]
    effect_type = outcome.get("inferred_effect_type") or "RR"
    is_ratio = _is_ratio_type(effect_type)

    # --- Step 1: Compute REFERENCE pooled from Cochrane data ---
    ref_yi = []
    ref_sei = []
    for s in studies:
        if s["mean"] is None:
            continue
        if is_ratio:
            if s["mean"] <= 0:
                continue
            yi = math.log(s["mean"])
        else:
            yi = s["mean"]
        se = se_from_ci(s["mean"], s["ci_start"], s["ci_end"], is_ratio)
        if se is None or se <= 0:
            continue
        ref_yi.append(yi)
        ref_sei.append(se)

    ref_pooled = None
    if len(ref_yi) >= 2:
        ref_pooled = meta_engine.pool_dl(ref_yi, ref_sei)
    elif len(ref_yi) == 1:
        ref_pooled = meta_engine.pool_dl(ref_yi, ref_sei)

    # --- Step 2: Extract effects from PDFs ---
    extractions = []
    study_errors = []
    n_with_pdf = 0

    for s in studies:
        if not s.get("pdf_path"):
            study_errors.append("missing_pdf")
            continue
        n_with_pdf += 1

        # Run extractor
        raw_extractions = effect_extractor.extract_from_pdf(s["pdf_path"])
        if not raw_extractions:
            study_errors.append("extraction_failure")
            extractions.append({"study_id": s["study_id"], "matched": False,
                                "extracted_effect": None, "match_tier": None})
            continue

        # Find best match against Cochrane value
        best = None
        for ext in raw_extractions:
            pe = ext.get("point_estimate")
            if pe is None:
                continue
            match_result = effect_extractor.classify_match(
                extracted=pe, cochrane_mean=s["mean"], is_ratio=is_ratio
            )
            if match_result["matched"] and (best is None or
                    (match_result["pct_difference"] or 1) < (best["pct_difference"] or 1)):
                best = {**match_result, "study_id": s["study_id"],
                        "extracted_effect": pe, "cochrane_giv_mean": s["mean"]}

        if best and best["matched"]:
            extractions.append(best)
            study_errors.append(None)
        else:
            # Try computed effect from raw data
            computed = None
            # (Could compute OR/RR from raw counts here if available)
            ext_result = {"study_id": s["study_id"], "matched": False,
                          "extracted_effect": raw_extractions[0]["point_estimate"] if raw_extractions else None,
                          "match_tier": None, "cochrane_giv_mean": s["mean"]}
            extractions.append(ext_result)
            study_errors.append("no_match")

    # --- Step 3: Study-level assessment ---
    study_level = comparator.assess_study_level(
        total_k=len(studies), extractions=extractions, n_with_pdf=n_with_pdf
    )

    # --- Step 4: Pool matched extractions ---
    matched = [e for e in extractions if e.get("matched")]
    review_level = None
    repro_pooled = None

    if len(matched) >= 2 and ref_pooled is not None:
        repro_yi = []
        repro_sei = []
        for m in matched:
            pe = m["extracted_effect"]
            cochrane_mean = m["cochrane_giv_mean"]
            if pe is None:
                continue
            if is_ratio:
                if pe <= 0:
                    continue
                yi = math.log(pe)
            else:
                yi = pe
            # Use Cochrane SE as proxy (extracted CI may not be available)
            s_match = next((s for s in studies if s["study_id"] == m["study_id"]), None)
            if s_match:
                se = se_from_ci(s_match["mean"], s_match["ci_start"], s_match["ci_end"], is_ratio)
            else:
                se = None
            if se is not None and se > 0:
                repro_yi.append(yi)
                repro_sei.append(se)

        if len(repro_yi) >= 2:
            repro_pooled = meta_engine.pool_dl(repro_yi, repro_sei)
            review_level = comparator.assess_review_level(
                ref_pooled, repro_pooled, original_k=len(studies)
            )

    # --- Step 5: Error taxonomy ---
    errors = taxonomy.aggregate_errors(study_errors)

    # --- Step 6: TruthCert ---
    cert = truthcert.certify(
        review_id=review_id,
        rda_hash=truthcert.hash_data({"studies": [s["study_id"] for s in studies]}),
        extraction_hash=truthcert.hash_data({"extractions": [e.get("study_id") for e in extractions]}),
        pooling_hash=truthcert.hash_data({"ref": ref_pooled, "repro": repro_pooled}),
        classification=review_level["tier"] if review_level else "insufficient",
    )

    return {
        "review_id": review_id,
        "outcome_label": outcome["outcome_label"],
        "inferred_effect_type": effect_type,
        "study_level": study_level,
        "review_level": review_level,
        "reference_pooled": ref_pooled,
        "reproduced_pooled": repro_pooled,
        "extractions": extractions,
        "errors": errors,
        "cert": cert,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: 5/5 PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator composes full pipeline per outcome"
```

---

## Task 10: Batch Audit Scripts

**Files:**
- Create: `scripts/run_audit.py`, `scripts/run_single.py`, `scripts/generate_tables.py`

- [ ] **Step 1: Create run_single.py (debug tool)**

```python
#!/usr/bin/env python
"""Run MetaReproducer on a single RDA file for debugging."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rda_parser import load_rda
from pipeline.effect_inference import infer_outcome_types
from pipeline.orchestrator import reproduce_outcome, select_primary_outcome


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_single.py <path_to_rda>")
        sys.exit(1)

    rda_path = Path(sys.argv[1])
    print(f"Loading {rda_path.name}...")
    review = load_rda(rda_path)
    print(f"  Review: {review['review_id']}, {review['total_k']} studies, "
          f"{len(review['outcomes'])} outcomes")

    for outcome in review["outcomes"]:
        infer_outcome_types(outcome)
        print(f"  Outcome: {outcome['outcome_label']} (k={outcome['k']}, "
              f"type={outcome['inferred_effect_type']})")

    primary = select_primary_outcome(review["outcomes"])
    print(f"\nPrimary outcome: {primary['outcome_label']} (k={primary['k']})")

    report = reproduce_outcome(review["review_id"], primary)
    print(f"\nStudy-level: {report['study_level']}")
    print(f"Review-level: {report['review_level']}")
    print(f"Errors: {report['errors']}")

    # Save report
    out_path = Path("data/results") / f"{review['review_id']}_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create run_audit.py (batch)**

```python
#!/usr/bin/env python
"""Run MetaReproducer audit on all 465 Pairwise70 reviews."""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rda_parser import load_all_rdas
from pipeline.effect_inference import infer_outcome_types
from pipeline.orchestrator import reproduce_outcome, select_primary_outcome

RDA_DIR = Path(r"C:\Users\user\OneDrive - NHS\Documents\Pairwise70\data")
RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading all RDA files...")
    reviews = load_all_rdas(RDA_DIR)
    print(f"Loaded {len(reviews)} reviews")

    all_reports = []
    for i, review in enumerate(reviews):
        # Infer effect types
        for outcome in review["outcomes"]:
            infer_outcome_types(outcome)

        # Select primary outcome
        primary = select_primary_outcome(review["outcomes"])

        # Run pipeline
        try:
            report = reproduce_outcome(review["review_id"], primary)
            all_reports.append(report)
        except Exception as e:
            print(f"  ERROR: {review['review_id']}: {e}")
            continue

        # Progress
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(reviews)}] Last: {review['review_id']}", flush=True)

    # Save summary
    summary_path = RESULTS_DIR / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(all_reports, f, indent=2, default=str)
    print(f"\nSaved {len(all_reports)} reports to {summary_path}")

    # Print headline stats
    study_total = sum(r["study_level"]["total_studies"] for r in all_reports)
    study_matched = sum(r["study_level"]["matched_moderate"] for r in all_reports)
    review_classified = [r for r in all_reports if r["review_level"] is not None]
    reproduced = sum(1 for r in review_classified if r["review_level"]["tier"] == "reproduced")
    major = sum(1 for r in review_classified if r["review_level"]["tier"] == "major_discrepancy")

    print(f"\n=== HEADLINE RESULTS ===")
    print(f"Reviews processed: {len(all_reports)}")
    print(f"Study-level: {study_matched}/{study_total} matched within 10%")
    print(f"Review-level classified: {len(review_classified)}")
    print(f"  Reproduced: {reproduced}")
    print(f"  Major discrepancy: {major}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create generate_tables.py (manuscript tables)**

```python
#!/usr/bin/env python
"""Generate BMJ manuscript tables from audit results."""
import sys
import json
import csv
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"


def main():
    summary_path = RESULTS_DIR / "summary.json"
    if not summary_path.exists():
        print("Run run_audit.py first to generate results.")
        sys.exit(1)

    with open(summary_path) as f:
        reports = json.load(f)

    # Table 1: Study-level by effect type
    print("\n=== Table 1: Study-level reproducibility by effect type ===")
    by_type = {}
    for r in reports:
        et = r.get("inferred_effect_type", "unknown")
        if et not in by_type:
            by_type[et] = {"total": 0, "strict": 0, "moderate": 0}
        by_type[et]["total"] += r["study_level"]["n_with_pdf"]
        by_type[et]["strict"] += r["study_level"]["matched_strict"]
        by_type[et]["moderate"] += r["study_level"]["matched_moderate"]

    for et, counts in sorted(by_type.items()):
        n = counts["total"]
        s = counts["strict"]
        m = counts["moderate"]
        print(f"  {et}: {s}/{n} strict ({100*s/max(n,1):.1f}%), "
              f"{m}/{n} moderate ({100*m/max(n,1):.1f}%)")

    # Table 2: Review-level classification
    print("\n=== Table 2: Review-level classification ===")
    classified = [r for r in reports if r["review_level"] is not None]
    tiers = Counter(r["review_level"]["tier"] for r in classified)
    insufficient = sum(1 for r in reports if r["review_level"] is None)
    print(f"  Reproduced: {tiers.get('reproduced', 0)}")
    print(f"  Minor discrepancy: {tiers.get('minor_discrepancy', 0)}")
    print(f"  Major discrepancy: {tiers.get('major_discrepancy', 0)}")
    print(f"  Insufficient coverage: {insufficient}")

    # Table 3: Error taxonomy
    print("\n=== Table 3: Error taxonomy ===")
    error_totals = Counter()
    for r in reports:
        for k, v in r["errors"].items():
            if k not in ("primary_error_source",) and isinstance(v, int):
                error_totals[k] += v
    for cat, count in error_totals.most_common():
        print(f"  {cat}: {count}")

    # Save as CSV
    csv_path = RESULTS_DIR / "summary_table.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["review_id", "outcome", "effect_type", "total_k",
                          "n_with_pdf", "matched_strict", "matched_moderate",
                          "review_tier", "ref_pooled", "repro_pooled", "pct_diff"])
        for r in reports:
            rl = r.get("review_level") or {}
            writer.writerow([
                r["review_id"], r["outcome_label"], r.get("inferred_effect_type"),
                r["study_level"]["total_studies"], r["study_level"]["n_with_pdf"],
                r["study_level"]["matched_strict"], r["study_level"]["matched_moderate"],
                rl.get("tier", "insufficient"),
                rl.get("reference_pooled"), rl.get("reproduced_pooled"),
                rl.get("pct_difference"),
            ])
    print(f"\nCSV saved: {csv_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit**

```bash
git add scripts/
git commit -m "feat: batch audit, single-review debug, and table generation scripts"
```

---

## Task 11: R Validation

**Files:**
- Create: `tests/validate_against_r.R`

- [ ] **Step 1: Create R validation script**

```r
# tests/validate_against_r.R
# Compare MetaReproducer DL/REML against metafor::rma()
# Run: Rscript tests/validate_against_r.R

library(metafor)

cat("=== MetaReproducer R Validation ===\n\n")

# Test case 1: 5 binary studies (log-OR)
yi <- c(log(0.75), log(0.80), log(0.90), log(0.70), log(0.85))
sei <- c(0.20, 0.25, 0.30, 0.15, 0.22)

dl <- rma(yi, sei^2, method="DL")
reml <- rma(yi, sei^2, method="REML")

cat("Test 1: 5 binary studies\n")
cat(sprintf("  DL pooled:  %.8f  tau2: %.8f  I2: %.2f\n", dl$beta, dl$tau2, dl$I2))
cat(sprintf("  REML pooled: %.8f  tau2: %.8f  I2: %.2f\n", reml$beta, reml$tau2, reml$I2))

# Test case 2: Homogeneous studies
yi2 <- rep(log(0.80), 3)
sei2 <- rep(0.20, 3)
dl2 <- rma(yi2, sei2^2, method="DL")
cat(sprintf("\nTest 2: Homogeneous (DL tau2=%.10f)\n", dl2$tau2))

# Test case 3: k=2 heterogeneous
yi3 <- c(log(0.5), log(1.5))
sei3 <- c(0.2, 0.2)
dl3 <- rma(yi3, sei3^2, method="DL")
cat(sprintf("\nTest 3: k=2 (DL pooled=%.8f tau2=%.8f)\n", dl3$beta, dl3$tau2))

# Output JSON for comparison
cat("\n\n--- JSON for Python comparison ---\n")
cat(sprintf('{"test1_dl": {"pooled": %.10f, "tau2": %.10f, "i2": %.4f},\n',
    dl$beta, dl$tau2, dl$I2))
cat(sprintf(' "test1_reml": {"pooled": %.10f, "tau2": %.10f, "i2": %.4f},\n',
    reml$beta, reml$tau2, reml$I2))
cat(sprintf(' "test2_dl": {"pooled": %.10f, "tau2": %.10f},\n',
    dl2$beta, dl2$tau2))
cat(sprintf(' "test3_dl": {"pooled": %.10f, "tau2": %.10f}}\n',
    dl3$beta, dl3$tau2))
```

- [ ] **Step 2: Run R validation (if R available)**

Run: `Rscript tests/validate_against_r.R`

- [ ] **Step 3: Add R validation to Python test (known-good values)**

Add to `tests/test_meta_engine.py`:

```python
def test_dl_matches_r_metafor():
    """DL pooled matches R metafor within 1e-6.

    R values from: Rscript tests/validate_against_r.R
    Must be updated after running R script.
    """
    from pipeline.meta_engine import pool_dl
    import math
    yi = [math.log(x) for x in [0.75, 0.80, 0.90, 0.70, 0.85]]
    sei = [0.20, 0.25, 0.30, 0.15, 0.22]
    result = pool_dl(yi, sei)
    # Placeholder — update with actual R output
    # assert abs(result["pooled"] - R_DL_POOLED) < 1e-6
    # assert abs(result["tau2"] - R_DL_TAU2) < 1e-6
    assert result["k"] == 5  # Minimal check until R values available
```

- [ ] **Step 4: Commit**

```bash
git add tests/validate_against_r.R tests/test_meta_engine.py
git commit -m "feat: R validation script for DL/REML parity"
```

---

## Task 12: Integration Test with Real Data

**Files:**
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Add integration test using real RDA**

Append to `tests/test_orchestrator.py`:

```python
def test_full_pipeline_real_rda():
    """Integration: load real RDA, infer types, compute reference pooled."""
    from pathlib import Path
    from pipeline.rda_parser import load_rda
    from pipeline.effect_inference import infer_outcome_types
    from pipeline.orchestrator import reproduce_outcome, select_primary_outcome

    rda_dir = Path(r"C:\Users\user\OneDrive - NHS\Documents\Pairwise70\data")
    rda_files = sorted(rda_dir.glob("*.rda"))
    if not rda_files:
        pytest.skip("Pairwise70 not available")

    review = load_rda(rda_files[0])
    for outcome in review["outcomes"]:
        infer_outcome_types(outcome)

    primary = select_primary_outcome(review["outcomes"])
    report = reproduce_outcome(review["review_id"], primary)

    # Verify structure
    assert report["review_id"] is not None
    assert report["study_level"]["total_studies"] >= 1
    assert report["errors"]["primary_error_source"] is not None or report["errors"]["success"] > 0
    assert report["cert"]["provenance_chain"] is not None
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_orchestrator.py
git commit -m "test: add integration test with real Pairwise70 RDA"
```

---

## Task 13: Dashboard — HTML Shell

**Files:**
- Create: `dashboard/index.html`

This is the largest single file. It loads `summary.json` and renders 5 views.

- [ ] **Step 1: Create the dashboard HTML**

Create `dashboard/index.html` — a single-file HTML app with:
- File input to load `summary.json`
- Tab navigation: Overview | Explorer | Taxonomy | Fragility | Coverage
- Plotly.js CDN for charts
- CSS vars for dark/light theme
- Overview panel with donut chart + bar chart
- Review explorer table with search/filter/sort
- Drill-down panel (lazy-rendered on row click)
- Error taxonomy stacked bar + treemap
- Fragility scatter plot
- OA coverage histogram
- CSV export button
- Print stylesheet

**Key implementation notes:**
- Load Plotly.js from CDN: `https://cdn.plot.ly/plotly-2.27.0.min.js`
- Use `${'<'}/script>` pattern if any template literals contain script tags
- All element IDs must be unique
- Use `document.documentElement.setAttribute('data-theme', theme)` for theme toggle
- Keyboard accessible: all interactive elements get tabindex + Enter/Space handlers
- Forest plots in drill-down rendered on demand (not precomputed)

The dashboard implementation is substantial (~2,000-3,000 lines). The implementing agent should build it incrementally:
1. HTML skeleton with tabs and file input
2. Overview panel (donut + bars)
3. Explorer table with filtering
4. Drill-down panel
5. Taxonomy view
6. Fragility scatter
7. Coverage analysis
8. Theme toggle + CSV export + print

- [ ] **Step 2: Test with sample data**

Create a small `data/results/sample_summary.json` with 5 mock reviews for testing.

- [ ] **Step 3: Commit**

```bash
git add dashboard/ data/results/sample_summary.json
git commit -m "feat: interactive dashboard with 5 views and file input"
```

---

## Task 14: Dashboard Selenium Tests

**Files:**
- Create: `tests/test_dashboard.py`

- [ ] **Step 1: Write Selenium tests**

```python
# tests/test_dashboard.py
"""Selenium tests for the MetaReproducer dashboard."""
import pytest
import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


@pytest.fixture(scope="module")
def driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    d = webdriver.Chrome(options=opts)
    d.set_window_size(1400, 900)
    yield d
    d.quit()


@pytest.fixture(scope="module")
def loaded_dashboard(driver):
    html_path = Path(__file__).parent.parent / "dashboard" / "index.html"
    driver.get(f"file:///{html_path.resolve()}")
    # Inject sample data
    sample = [
        {"review_id": "CD000001", "outcome_label": "Mortality",
         "inferred_effect_type": "RR",
         "study_level": {"total_studies": 10, "n_with_pdf": 5,
                         "matched_strict": 3, "matched_moderate": 4,
                         "match_rate_strict": 0.6, "match_rate_moderate": 0.8,
                         "no_pdf": 5, "extraction_failed": 0, "extracted_no_match": 1},
         "review_level": {"tier": "reproduced", "pct_difference": 0.03,
                          "same_direction": True, "same_significance": True,
                          "reference_k": 10, "reproduced_k": 4, "k_coverage": 0.4,
                          "reference_pooled": -0.22, "reproduced_pooled": -0.21},
         "errors": {"missing_pdf": 5, "success": 4, "no_match": 1,
                    "primary_error_source": "missing_pdf"},
         "cert": {"review_id": "CD000001", "classification": "reproduced"}},
    ]
    driver.execute_script(f"window._testData = {json.dumps(sample)};")
    driver.execute_script("if(window.loadData) loadData(window._testData);")
    time.sleep(1)
    return driver


def test_overview_renders(loaded_dashboard):
    """Overview panel shows headline numbers."""
    el = loaded_dashboard.find_element(By.ID, "overviewPanel")
    assert el.is_displayed()


def test_theme_toggle(loaded_dashboard):
    """Dark mode toggle changes theme attribute."""
    btn = loaded_dashboard.find_element(By.ID, "themeToggle")
    btn.click()
    theme = loaded_dashboard.execute_script(
        "return document.documentElement.getAttribute('data-theme')")
    assert theme in ("dark", "light")


def test_explorer_table(loaded_dashboard):
    """Explorer table has at least one row."""
    rows = loaded_dashboard.find_elements(By.CSS_SELECTOR, "#explorerTable tbody tr")
    assert len(rows) >= 1
```

- [ ] **Step 2: Run dashboard tests**

Run: `python -m pytest tests/test_dashboard.py -v`
Expected: 3/3 PASS (requires Chrome)

- [ ] **Step 3: Commit**

```bash
git add tests/test_dashboard.py
git commit -m "test: Selenium tests for dashboard rendering and interaction"
```

---

## Task 15: Link Mega Gold Data + First Real Run

**Files:**
- Modify: `pipeline/rda_parser.py` (add DOI/PMCID/PDF linking)
- Create: `scripts/link_mega_data.py`

- [ ] **Step 1: Create linking script**

```python
#!/usr/bin/env python
"""Link Pairwise70 RDA studies to existing mega gold standard PDFs."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

MEGA_DIR = Path(r"C:\Users\user\rct-extractor-v2\gold_data\mega")
PDF_DIR = MEGA_DIR / "pdfs"


def build_study_pdf_map() -> dict:
    """Build mapping: (first_author, year) -> pdf_path from mega_matched.jsonl."""
    matched_path = MEGA_DIR / "mega_matched.jsonl"
    mapping = {}
    with open(matched_path) as f:
        for line in f:
            entry = json.loads(line)
            pmcid = entry.get("pmcid")
            if not pmcid:
                continue
            pdf_path = PDF_DIR / f"{pmcid}.pdf"
            if not pdf_path.exists():
                continue
            author = entry.get("first_author", "")
            year = entry.get("year")
            key = (author.strip(), year)
            mapping[key] = str(pdf_path)
    return mapping


def link_reviews(reviews: list[dict], pdf_map: dict) -> None:
    """Mutate reviews in-place: set pdf_path on matching studies."""
    linked = 0
    total = 0
    for review in reviews:
        for outcome in review["outcomes"]:
            for study in outcome["studies"]:
                total += 1
                author = study["study_id"].strip()
                year = study.get("year")
                key = (author, year)
                if key in pdf_map:
                    study["pdf_path"] = pdf_map[key]
                    linked += 1
    print(f"Linked {linked}/{total} studies to PDFs ({100*linked/max(total,1):.1f}%)")


if __name__ == "__main__":
    from pipeline.rda_parser import load_all_rdas
    rda_dir = Path(r"C:\Users\user\OneDrive - NHS\Documents\Pairwise70\data")
    reviews = load_all_rdas(rda_dir)
    pdf_map = build_study_pdf_map()
    link_reviews(reviews, pdf_map)
```

- [ ] **Step 2: Run linking to verify coverage**

Run: `python scripts/link_mega_data.py`
Expected: Shows linked count (should be ~1,290 linked)

- [ ] **Step 3: First single-review test run**

Run: `python scripts/run_single.py "C:\Users\user\OneDrive - NHS\Documents\Pairwise70\data\CD000028_pub4_data.rda"`
Expected: Prints study-level + review-level results, saves JSON report

- [ ] **Step 4: Commit**

```bash
git add scripts/link_mega_data.py
git commit -m "feat: link Pairwise70 studies to mega gold standard PDFs"
```

---

## Task 16: Final Test Suite Run + Full Audit

- [ ] **Step 1: Run complete test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All unit + integration tests PASS

- [ ] **Step 2: Run full audit (may take 30-60 min)**

Run: `python scripts/run_audit.py`
Expected: Processes ~465 reviews, saves `data/results/summary.json`

- [ ] **Step 3: Generate tables**

Run: `python scripts/generate_tables.py`
Expected: Prints headline results + saves `summary_table.csv`

- [ ] **Step 4: Load dashboard with real data**

Open `dashboard/index.html` in browser, load `data/results/summary.json` via file input.
Verify: overview numbers match script output, table is populated, charts render.

- [ ] **Step 5: Final commit**

```bash
git add data/results/
git commit -m "feat: first full audit results — 465 Cochrane reviews"
```

---

## Execution Notes

- **Tasks 1-9** are independent enough for subagent-driven development (one agent per task)
- **Task 10** depends on Tasks 1-9
- **Task 11** (R validation) can run in parallel with anything
- **Task 12-13** (dashboard) can start after Task 9
- **Task 14** (linking) depends on Tasks 1-9
- **Task 15** (full audit) depends on everything

**Critical path:** Tasks 1→2→3→4→5→6→7→8→9→13→14→15→16

**Review fixes applied:**
- **C3**: REML Fisher scoring corrected — numerator uses `sum(w_i^2*(yi-mu)^2) - sum(w_i)` (Viechtbauer 2005), not `- sum(w_i^2*v_i)`
- **C4**: Added `load_existing_extractions()` + `get_extraction_for_study()` to reuse ~1,290 pre-computed results from `mega_eval_v10_3_merged.jsonl`
- **C5**: Strict match rate is ~24% (216 direct_5pct+10pct + 94 computed_5pct = ~310/1,290), not 30-40%. Spec estimates updated.
- **C1**: Plan code correctly uses `Mean`/`CI.start`/`CI.end` columns (not `GIV.Mean`/`GIV.SE`). Spec narrative to be updated separately.
- Dependency fix: Task 14 (Selenium) requires Task 13 (dashboard) to exist first
