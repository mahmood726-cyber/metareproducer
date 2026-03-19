# MetaReproducer — Design Specification

## 1. Problem Statement

The reproducibility crisis in meta-analyses is well-documented but has never been computationally audited at scale. Manual reproducibility checks cover 20-50 reviews. No automated system exists to re-derive a published meta-analysis from its source trials and compare results.

## 2. Goal

Build a Python pipeline + HTML dashboard that:
1. Takes 501 Cochrane reviews (Pairwise70 RDA dataset)
2. Re-extracts effect sizes from source trial PDFs using RCT Extractor v10.3
3. Re-runs pooled meta-analysis (DL + REML)
4. Classifies reproducibility (Reproduced / Minor / Major discrepancy)
5. Produces an error taxonomy
6. Visualizes results in an interactive dashboard
7. Supports a BMJ manuscript reporting the findings

## 3. Scope

**In scope:**
- Cochrane reviews only (structured RDA data)
- Pairwise70 dataset (501 reviews, cross-domain medicine)
- Re-extraction via existing RCT Extractor v10.3
- DL + REML pooled meta-analysis in Python
- Three-tier reproducibility classification
- Error taxonomy
- Single-file HTML dashboard
- BMJ manuscript

**Out of scope (future work):**
- Non-Cochrane systematic reviews
- NLP parsing of review PDFs to identify included studies
- Real-time CT.gov monitoring / living observatory
- Non-English reviews

## 4. Architecture

```
C:\Users\user\Downloads\MetaReproducer\
├── pipeline/
│   ├── orchestrator.py          # Main: RDA -> ReproducibilityReport
│   ├── rda_parser.py            # Extract studies + Cochrane pooled results from RDA
│   ├── effect_extractor.py      # Wrapper around RCT Extractor v10.3
│   ├── meta_engine.py           # DL + REML pooled analysis (Python)
│   ├── comparator.py            # Three-tier reproducibility classification
│   ├── taxonomy.py              # Error taxonomy classification
│   └── truthcert.py             # SHA-256 provenance chain per review
├── scripts/
│   ├── run_audit.py             # Batch: all 501 reviews -> results JSON
│   ├── run_single.py            # Debug: one review at a time
│   └── generate_tables.py       # BMJ manuscript tables from results
├── data/
│   ├── rda/                     # Symlink to Pairwise70 RDA files
│   ├── pdfs/                    # Symlink to existing downloaded PDFs
│   └── results/                 # Output: per-review JSON + summary CSV
├── dashboard/
│   └── index.html               # Single-file interactive dashboard
├── paper/
│   └── metareproducer_bmj.md    # Manuscript
├── tests/
│   ├── test_rda_parser.py
│   ├── test_meta_engine.py
│   ├── test_comparator.py
│   ├── test_taxonomy.py
│   ├── test_truthcert.py
│   ├── test_orchestrator.py
│   └── test_dashboard.py        # Selenium tests for dashboard
└── CLAUDE.md
```

## 5. Pipeline Modules

### 5.1 rda_parser.py

**Input:** Path to Cochrane RDA file.

**Output:** `CochraneReview` dataclass:
```python
@dataclass
class CochraneStudy:
    study_id: str           # e.g., "Smith 2020"
    effect_type: str        # OR, RR, HR, MD, SMD
    effect_size: float      # Cochrane-computed effect
    ci_lower: float
    ci_upper: float
    se: float
    weight: float           # Cochrane-assigned weight
    events_int: int | None  # 2x2 count data (if available)
    total_int: int | None
    events_ctrl: int | None
    total_ctrl: int | None
    doi: str | None         # From mega_doi_lookup output
    pmcid: str | None
    pdf_path: str | None

@dataclass
class CochraneReview:
    review_id: str
    title: str
    therapeutic_area: str   # Inferred from Cochrane group or keywords
    comparison: str         # e.g., "Drug A vs Placebo"
    outcome: str            # e.g., "All-cause mortality"
    effect_type: str        # OR, RR, HR, MD, SMD
    model: str              # Fixed or Random
    pooled_effect: float    # Cochrane pooled estimate
    pooled_ci_lower: float
    pooled_ci_upper: float
    pooled_se: float
    tau2: float
    i2: float
    k: int                  # Number of studies
    studies: list[CochraneStudy]
```

**Reuses:** Logic from `build_mega_gold.py` (RDA loading, study extraction) and `mega_doi_lookup.py` output (DOI/PMCID mapping).

### 5.2 effect_extractor.py

**Input:** `CochraneStudy` with `pdf_path`.

**Output:** `ExtractedEffect` dataclass:
```python
@dataclass
class ExtractedEffect:
    study_id: str
    extracted_effect: float | None
    extracted_ci_lower: float | None
    extracted_ci_upper: float | None
    extracted_effect_type: str | None
    match_tier: str | None      # direct_5pct, reciprocal_5pct, etc.
    extraction_method: str      # text, table, computation, llm
    cochrane_effect: float
    pct_difference: float | None
    matched: bool
```

**Implementation:** Thin wrapper that calls the existing RCT Extractor pipeline. Reuses the matching logic from `mega_evaluate_v2.py` (12-tier matching with reciprocal, signflip, scale normalization). Does NOT re-implement extraction — imports from `rct-extractor-v2`.

### 5.3 meta_engine.py

**Input:** List of `ExtractedEffect` (matched studies only).

**Output:** `PooledResult` dataclass:
```python
@dataclass
class PooledResult:
    method: str             # "DL" or "REML"
    pooled_effect: float
    pooled_ci_lower: float
    pooled_ci_upper: float
    pooled_se: float
    tau2: float
    i2: float
    q_stat: float
    q_pvalue: float
    k: int                  # Number of studies included
    prediction_interval: tuple[float, float] | None
```

**Implementation:** ~150 lines of Python. DerSimonian-Laird random-effects and REML (Newton-Raphson/Fisher scoring). The user has implemented these algorithms in JS (multiple codebases) and Python (IPD-QMA). This is a clean Python implementation for the pipeline.

**Key decisions:**
- Operates on log scale for ratio measures (OR, RR, HR), raw scale for MD/SMD
- SE derived from CI: `se = (ln(ci_upper) - ln(ci_lower)) / (2 * 1.96)` for ratio; `(ci_upper - ci_lower) / (2 * 1.96)` for difference
- When extracted CI unavailable, uses Cochrane SE as fallback
- Both DL and REML computed; DL is primary (matches most Cochrane analyses)

### 5.4 comparator.py

**Input:** `CochraneReview` + `PooledResult` from MetaReproducer.

**Output:** `ReproducibilityClassification`:
```python
@dataclass
class ReproducibilityClassification:
    tier: str               # "reproduced", "minor_discrepancy", "major_discrepancy", "unable"
    cochrane_pooled: float
    reproduced_pooled: float
    pct_difference: float
    same_direction: bool
    same_significance: bool  # Both p<0.05 or both p>=0.05
    cochrane_k: int
    reproduced_k: int       # May be < cochrane_k if some extractions failed
    k_coverage: float       # reproduced_k / cochrane_k
    details: str            # Human-readable explanation
```

**Classification rules:**
- **Reproduced**: pooled effect within 5% AND same direction AND same significance (p<0.05 threshold) AND k_coverage >= 0.75
- **Minor discrepancy**: same direction AND same significance, but effect differs >5% OR k_coverage 0.50-0.74
- **Major discrepancy**: different significance conclusion OR different direction
- **Unable**: k_coverage < 0.50 (too few studies extracted to meaningfully compare)

The 5% threshold is justified by the RCT Extractor's validated accuracy at this tolerance. The k_coverage >= 0.75 requirement ensures the reproduced analysis includes enough of the original studies to be a fair comparison.

### 5.5 taxonomy.py

**Input:** Per-study extraction results + overall classification.

**Output:** `ErrorTaxonomy`:
```python
@dataclass
class ErrorTaxonomy:
    review_id: str
    classification: str
    primary_error_source: str   # One of the categories below
    error_counts: dict[str, int]
    error_details: list[dict]   # Per-study error breakdown
```

**Error categories:**
1. **extraction_failure** — PDF could not be parsed (no text, scanned image, corrupt)
2. **no_match** — Effect extracted but doesn't match Cochrane (wrong outcome, adjusted vs unadjusted)
3. **scale_mismatch** — Effect type differs (OR extracted, Cochrane has RR)
4. **direction_flip** — Extracted effect has opposite direction (arm swap, 1/OR)
5. **missing_pdf** — No OA PDF available for the study
6. **computation_gap** — Cochrane computed from raw counts; PDF reports different statistic
7. **significance_shift** — Individual effects match but pooled result crosses p=0.05

### 5.6 truthcert.py

**Input:** Complete `ReproducibilityReport` for a review.

**Output:** TruthCert bundle (JSON):
```python
{
    "review_id": "CD001234",
    "pipeline_version": "1.0.0",
    "timestamp": "2026-03-20T14:30:00Z",
    "rda_hash": "sha256:abc123...",       # Hash of input RDA file
    "pdf_hashes": {"study_1.pdf": "sha256:def456...", ...},
    "extractor_version": "10.3",
    "classification": "reproduced",
    "cochrane_pooled": 0.85,
    "reproduced_pooled": 0.83,
    "provenance_chain": [
        {"step": "rda_parse", "hash": "...", "timestamp": "..."},
        {"step": "extraction", "hash": "...", "timestamp": "..."},
        {"step": "pooling", "hash": "...", "timestamp": "..."},
        {"step": "comparison", "hash": "...", "timestamp": "..."}
    ]
}
```

### 5.7 orchestrator.py

Composes all modules:
```python
def reproduce_review(rda_path: str, pdf_dir: str) -> ReproducibilityReport:
    # 1. Parse Cochrane RDA
    review = rda_parser.parse(rda_path)

    # 2. Extract effects from source PDFs
    extractions = []
    for study in review.studies:
        if study.pdf_path:
            ext = effect_extractor.extract(study)
            extractions.append(ext)

    # 3. Pool matched extractions
    matched = [e for e in extractions if e.matched]
    if len(matched) < 2:
        return ReproducibilityReport(classification="unable", ...)

    pooled_dl = meta_engine.pool(matched, method="DL", effect_type=review.effect_type)
    pooled_reml = meta_engine.pool(matched, method="REML", effect_type=review.effect_type)

    # 4. Compare against Cochrane
    classification = comparator.classify(review, pooled_dl)

    # 5. Error taxonomy
    errors = taxonomy.classify_errors(review, extractions)

    # 6. TruthCert
    cert = truthcert.certify(review, extractions, pooled_dl, classification)

    return ReproducibilityReport(
        review=review, extractions=extractions,
        pooled_dl=pooled_dl, pooled_reml=pooled_reml,
        classification=classification, errors=errors, cert=cert
    )
```

## 6. Dashboard Design

Single-file HTML app (`dashboard/index.html`). Loads `data/results/summary.json` via file input. No server, no build step. Plotly.js for charts. CSS vars for dark/light theme.

### 6.1 Overview Panel
- Headline numbers: "X/501 Reproduced (Y%)" | "Z Major Discrepancies" | "W Unable"
- Donut chart: Reproduced / Minor / Major / Unable (color-coded)
- Therapeutic area breakdown (horizontal bar chart, sorted by reproducibility rate)

### 6.2 Review Explorer
- Searchable, sortable, filterable table (all 501 reviews)
- Columns: Title, Area, k, Cochrane Effect, Reproduced Effect, % Diff, Classification (badge), Error Type
- Filters: classification tier, therapeutic area, effect type (OR/HR/MD/SMD), review size
- Click row -> drill-down

### 6.3 Drill-Down Panel
- Side-by-side forest plots (Cochrane vs MetaReproducer)
- Per-study extraction table with match tiers
- TruthCert provenance chain display
- Error taxonomy for this review

### 6.4 Error Taxonomy View
- Stacked bar chart: error categories across all reviews
- Treemap: hierarchical error breakdown
- Filterable by therapeutic area, effect type, review size

### 6.5 Fragility Landscape
- Scatter plot: X = k (study count), Y = % effect difference
- Colored by classification tier, sized by total sample size
- Hover shows review title + key stats
- Highlights reviews near significance boundary

### 6.6 Interactions
- Dark/light theme toggle (CSS vars + data-theme attribute)
- CSV export of results table
- PDF print stylesheet (A4, hides UI chrome)
- Keyboard accessible (tab navigation, Enter/Space activation)

## 7. Data Flow

```
Pairwise70 RDA files (501)
        |
        v
   rda_parser.py -----> CochraneReview (studies + pooled results)
        |
        v
   effect_extractor.py --> ExtractedEffect per study (calls RCT Extractor)
        |
        v
   meta_engine.py ------> PooledResult (DL + REML)
        |
        v
   comparator.py -------> ReproducibilityClassification (3-tier)
        |
        v
   taxonomy.py ---------> ErrorTaxonomy (7 categories)
        |
        v
   truthcert.py --------> TruthCert bundle (SHA-256 provenance)
        |
        v
   results/summary.json --> dashboard/index.html
                        --> paper/tables + figures
```

## 8. Reproducibility Classification

| Tier | Criteria | Expected % |
|------|----------|------------|
| Reproduced | Effect within 5%, same direction, same significance, k_coverage >= 75% | ~60-70% |
| Minor discrepancy | Same direction + significance, effect >5% OR k_coverage 50-74% | ~15-20% |
| Major discrepancy | Different significance OR different direction | ~5-10% |
| Unable | k_coverage < 50% (too few PDFs extracted) | ~10-15% |

Expected percentages are rough estimates based on RCT Extractor v10.3 accuracy (94.6% individual match rate). The actual numbers are the research finding.

## 9. Testing Strategy

### Unit tests (pytest)
- `test_rda_parser.py`: Parse 3-5 known RDA files, verify study counts + effect values
- `test_meta_engine.py`: DL + REML on known datasets (compare against R metafor within 1e-6)
- `test_comparator.py`: Classification logic with edge cases (borderline 5%, direction flip, k=1)
- `test_taxonomy.py`: Error categorization with synthetic data
- `test_truthcert.py`: Hash chain integrity, deterministic output

### Integration tests
- `test_orchestrator.py`: End-to-end on 3 known reviews with known expected results
- Golden output comparison: save expected JSON, compare on re-run

### Dashboard tests (Selenium)
- Load summary.json, verify overview numbers render
- Filter by classification, verify table updates
- Click drill-down, verify forest plot renders
- Dark mode toggle, CSV export, print layout

### R validation
- Compare DL/REML pooled results against `metafor::rma()` for 10+ reviews
- Tolerance: 1e-6 for effect, 1e-4 for tau2/I2

## 10. BMJ Manuscript Outline

**Title:** "Computational Reproducibility of Cochrane Systematic Reviews: An Automated Audit of 501 Meta-Analyses"

**Abstract** (~250 words): Objective, Design (computational reproducibility study), Setting (Cochrane Library), Data (501 reviews from Pairwise70), Main outcome (reproducibility rate), Results (headline numbers), Conclusion.

**Introduction** (~500 words): Reproducibility crisis, meta-analyses as foundation of EBM, no prior computational audit at scale, gap this fills.

**Methods** (~1000 words):
- Data source: Pairwise70 (501 Cochrane reviews, cross-domain)
- Extraction pipeline: RCT Extractor v10.3 (validated 94.6%)
- Re-analysis: DL random-effects (matching Cochrane default)
- Classification: three-tier system (reproduced/minor/major)
- Error taxonomy: 7 categories
- Software: MetaReproducer (open source, TruthCert provenance)

**Results** (~1500 words):
- Overall reproducibility rate (primary outcome)
- Breakdown by therapeutic area (Table 1)
- Breakdown by effect type (Table 2)
- Error taxonomy distribution (Figure 2)
- Factors associated with non-reproducibility (logistic regression: k, effect type, year, area)
- Case studies: 3 major discrepancies examined in detail

**Discussion** (~1000 words):
- Comparison to prior manual reproducibility studies
- Why reviews fail (taxonomy insights)
- Implications for Cochrane workflow
- Limitations: OA PDFs only, single pipeline, adjusted vs unadjusted effects
- Implications for practice: confidence in Cochrane conclusions

**Figures:**
1. Overview: donut chart + therapeutic area bars
2. Error taxonomy: stacked bars
3. Fragility landscape: scatter plot
4. Case study: side-by-side forest plots (1 reproduced, 1 major discrepancy)

**Tables:**
1. Reproducibility by therapeutic area
2. Reproducibility by effect measure type
3. Error taxonomy counts
4. Logistic regression: predictors of non-reproducibility

## 11. Dependencies

- Python 3.11+ (not 3.13 due to WMI deadlock risk)
- RCT Extractor v10.3 (imported as library from `C:\Users\user\rct-extractor-v2\`)
- numpy, scipy (DL/REML computation)
- pytest (testing)
- Selenium + Chrome (dashboard tests)
- R + metafor (validation only, not in main pipeline)

## 12. Key Risks

| Risk | Mitigation |
|------|-----------|
| RCT Extractor's 94.6% is on individual effects; pooled-level reproducibility may differ | k_coverage threshold ensures only reviews with sufficient extraction are classified |
| Cochrane uses various effect measures and models | RDA files contain the model specification; match Cochrane's model choice |
| Adjusted vs unadjusted effects (papers report adjusted, Cochrane uses raw counts) | Document as known limitation; taxonomy captures this as "computation_gap" |
| OA PDF availability may be biased (newer/larger trials more likely OA) | Report OA coverage rate; sensitivity analysis on available subset |
| BMJ word limits (~4000 words total) | Tight prose, supplementary appendix for methods detail, dashboard as interactive supplement |

## 13. Success Criteria

1. Pipeline processes all 501 reviews without manual intervention
2. At least 350/501 reviews (70%) have k_coverage >= 50% (i.e., classifiable)
3. R validation passes for DL/REML (10+ reviews, tolerance 1e-6)
4. Dashboard renders correctly with full dataset
5. All tests pass (unit + integration + dashboard)
6. TruthCert chain verifiable for every classified review
7. Manuscript draft complete with real numbers
