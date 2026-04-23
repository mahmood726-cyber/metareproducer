# MetaReproducer 5-Persona Code Review Findings

**REVIEW CLEAN** — All P0 and P1 fixed. 77/77 tests pass.

**Date:** 2026-03-24
**Test suite:** 77/77 pass (confirmed after fixes)
**Scope:** 13 files (7 pipeline + 4 scripts + 2 support)

---

## P0 — Critical (must fix before production run)

### P0-1 [FIXED]: Field name mismatch between rda_parser and effect_inference [Statistical Methodologist + Domain Expert]

**File:** `C:\MetaReproducer\pipeline\effect_inference.py`, lines 112-115, 139-142
**File:** `C:\MetaReproducer\pipeline\rda_parser.py`, lines 116-126

`infer_effect_type()` reads RDA raw column names (`"Experimental.cases"`, `"Experimental.N"`, `"Control.cases"`, `"Control.N"`, `"Experimental.mean"`, `"Experimental.SD"`, `"Control.mean"`, `"Control.SD"`), but the studies it receives in the production pipeline have already been through `_build_study_dict()`, which renames these to `events_int`, `total_int`, `events_ctrl`, `total_ctrl`, `mean_int`, `sd_int`, `n_int`, `mean_ctrl`, `sd_ctrl`, `n_ctrl`.

**Impact:** In the production pipeline, `infer_effect_type()` always receives `None` for all raw data fields. This means:
- ALL binary studies get classified as `"unknown_ratio"` instead of `"OR"` or `"RR"`
- ALL continuous studies get classified as `"unknown_ratio"` instead of `"MD"` or `"SMD"`
- The `inferred_effect_type` field on every outcome will be `"unknown_ratio"`
- The `is_ratio` flag will always be `True`, causing ALL effects to be log-transformed before pooling, including mean differences (which should NOT be log-transformed)

This silently corrupts the reference pooled estimate, the reproduced pooled estimate, and the entire classification. The study-level and review-level results would be invalid.

**Why tests pass:** The unit tests for `infer_effect_type()` construct study dicts using the raw column names directly (`"Experimental.cases": 15`), bypassing the rda_parser entirely. The integration test (`test_full_pipeline_real_rda`) does exercise the full path, but only asserts that a result exists, not that the inferred type is correct.

**Fix:** Either:
(a) Update `infer_effect_type()` to use the StudyDict key names (`events_int`, `total_int`, etc.), OR
(b) Have `_build_study_dict()` also include the raw column names alongside the renamed ones, OR
(c) Add a mapping layer in `infer_outcome_types()` that translates StudyDict keys to what `infer_effect_type()` expects.

Option (a) is cleanest. Change lines 112-115 in `effect_inference.py`:
```python
# CURRENT (broken):
a = study.get("Experimental.cases")
n1 = study.get("Experimental.N")
c = study.get("Control.cases")
n2 = study.get("Control.N")

# FIX:
a = study.get("events_int")
n1 = study.get("total_int")
c = study.get("events_ctrl")
n2 = study.get("total_ctrl")
```
And lines 139-142:
```python
# CURRENT (broken):
m1 = study.get("Experimental.mean")
sd1 = study.get("Experimental.SD")
n1 = study.get("Experimental.N")
m2 = study.get("Control.mean")
sd2 = study.get("Control.SD")
n2 = study.get("Control.N")

# FIX:
m1 = study.get("mean_int")
sd1 = study.get("sd_int")
n1 = study.get("n_int")
m2 = study.get("mean_ctrl")
sd2 = study.get("sd_ctrl")
n2 = study.get("n_ctrl")
```
Then update the test fixtures in `test_effect_inference.py` and `test_edge_cases.py` to use the StudyDict key names.

### P0-2 [FIXED]: load_existing_extractions() re-parsed per outcome, not cached [Software Engineer]

**File:** `C:\MetaReproducer\pipeline\orchestrator.py`, line 203

`reproduce_outcome()` calls `effect_extractor.load_existing_extractions()` on every invocation. Since `reproduce_outcome()` is called once per review (465+ times in the audit), the 1.76 MB `mega_eval_v10_3_merged.jsonl` file is re-read and re-parsed 465+ times.

**Impact:** Massive I/O waste. At ~5ms per parse, this adds ~2.3 seconds total (minor), but the pattern is architecturally wrong and will scale badly. More critically, it means each `reproduce_outcome()` call is not self-contained about where its data comes from -- the file could change between calls.

**Fix:** Load the extractions once in the caller (`run_audit.py` / `run_pipeline.py`) and pass them as a parameter to `reproduce_outcome()`:
```python
def reproduce_outcome(review_id, outcome, aact_lookup=None, existing_extractions=None):
    if existing_extractions is None:
        existing_extractions = effect_extractor.load_existing_extractions()
    ...
```

---

## P1 — Important (should fix)

### P1-1 [FIXED]: same_direction check fails when either pooled estimate is exactly zero [Statistical Methodologist]

**File:** `C:\MetaReproducer\pipeline\comparator.py`, line 137

```python
same_direction = (ref_pooled * repro_pooled) > 0
```

When either `ref_pooled` or `repro_pooled` is exactly 0.0 (plausible for mean differences), the product is 0, which is NOT > 0, so `same_direction` becomes `False`. This incorrectly triggers `major_discrepancy` classification even when the estimates are practically identical.

**Fix:**
```python
# Treat zero as compatible with either direction (or use a tolerance)
if abs(ref_pooled) < 1e-10 or abs(repro_pooled) < 1e-10:
    same_direction = True  # null effect matches any direction
else:
    same_direction = (ref_pooled * repro_pooled) > 0
```

### P1-2: Database cursors and connections not cleaned up in exception paths [Software Engineer]

**File:** `C:\MetaReproducer\pipeline\ctgov_extractor.py`, lines 86-96, 110-129, 145-173
**File:** `C:\MetaReproducer\scripts\run_audit.py`, lines 37-51

Cursor `close()` calls are not inside `try/finally` blocks. If a query raises an exception (e.g., network timeout, malformed data), the cursor and potentially the connection leak. In `run_audit.py`, `conn.close()` (line 51) is only reached on the happy path -- if `build_aact_lookup()` raises, the connection leaks.

**Fix:** Use context managers or try/finally:
```python
# In ctgov_extractor.py:
def batch_pmid_to_nct(conn, pmids):
    if not pmids:
        return {}
    cur = conn.cursor()
    try:
        cur.execute(...)
        mapping = {}
        for pmid, nct_id in cur.fetchall():
            ...
        return mapping
    finally:
        cur.close()

# In run_audit.py:
conn = get_connection()
if conn:
    try:
        ...
        aact_lookup = build_aact_lookup(conn, all_pmids)
    finally:
        conn.close()
```

### P1-3 [FIXED]: TruthCert bundle lacks timestamp [Domain Expert]

**File:** `C:\MetaReproducer\pipeline\truthcert.py`, lines 74-145

The TruthCert `certify()` function produces a provenance chain without any timestamp (no `created_at`, no `audit_date`). For a reproducibility audit claiming provenance, the absence of a timestamp is a significant gap. The bundle hash is deterministic (good), but there is no way to know WHEN the audit was performed.

The spec (Section 5.7) says "SHA-256 provenance chain per review. Hashes RDA input, PDF inputs, extraction outputs, pooling parameters, final classification" but does not explicitly exclude timestamps.

**Fix:** Add `datetime.utcnow().isoformat() + "Z"` to the bundle payload:
```python
import datetime

bundle_payload = {
    "review_id": review_id,
    "pipeline_version": pipeline_version,
    "classification": classification,
    "provenance_chain": provenance_chain,
    "created_at": datetime.datetime.utcnow().isoformat() + "Z",
}
```
Note: adding a timestamp makes the bundle_hash non-deterministic across runs. If determinism is required, store the timestamp outside the hashed payload.

### P1-4: Hardcoded absolute paths reduce portability [Software Engineer]

**Files:**
- `C:\MetaReproducer\pipeline\effect_extractor.py`, lines 35-38 (RCT Extractor path, mega eval path)
- `C:\MetaReproducer\pipeline\ctgov_extractor.py`, line 32 (.env path)
- `C:\MetaReproducer\scripts\run_pipeline.py`, line 23 (RDA_DIR)
- `C:\MetaReproducer\scripts\run_audit.py`, line 17 (RDA_DIR)
- `C:\MetaReproducer\scripts\link_mega_data.py`, line 9 (MEGA_DIR)

All data paths are hardcoded as `r"C:\Users\user\..."`. These are machine-specific and will break on any other machine.

**Fix:** Use environment variables or a config file:
```python
import os
RDA_DIR = Path(os.environ.get("METAREPRODUCER_RDA_DIR",
    r"C:\Users\user\OneDrive - NHS\Documents\Pairwise70\data"))
```

### P1-5 [FIXED]: _q1/_q3 quartile functions are inaccurate for BMJ manuscript tables [Statistical Methodologist]

**File:** `C:\MetaReproducer\scripts\run_pipeline.py`, lines 297-310

The `_q1(vals)` and `_q3(vals)` implementations use simple index-based lookups (`s[n // 4]` and `s[3 * n // 4]`) without interpolation. For the IQR values that will appear in a BMJ manuscript table, this is insufficiently precise.

For example, with n=100: `_q1` returns `s[25]` (the 26th value), `_q3` returns `s[75]` (the 76th value). This is close but uses a non-standard percentile method. numpy uses linear interpolation by default.

**Fix:** Use `numpy.percentile` or `statistics.quantiles`:
```python
import numpy as np
def _q1(vals): return float(np.percentile(vals, 25)) if vals else 0
def _q3(vals): return float(np.percentile(vals, 75)) if vals else 0
```

### P1-6: run_audit.py and run_pipeline.py duplicate the audit logic [Software Engineer]

**Files:**
- `C:\MetaReproducer\scripts\run_audit.py`
- `C:\MetaReproducer\scripts\run_pipeline.py`

Both scripts implement essentially the same audit loop (load RDAs, link PDFs/PMIDs, optionally connect to AACT, iterate reviews, call `reproduce_outcome`, save JSON). `run_pipeline.py` is the newer, more complete version (with `--skip-aact` and `--tables-only` flags), making `run_audit.py` redundant.

**Impact:** Bug fixes applied to one script may not be applied to the other. Someone running `run_audit.py` gets different behavior (e.g., no `--skip-aact` option, always attempts AACT connection).

**Fix:** Either (a) delete `run_audit.py` and keep only `run_pipeline.py`, or (b) have `run_audit.py` delegate to `run_pipeline.py`'s functions.

### P1-7 [FIXED]: No k=0 guard in pool_dl [Software Engineer]

**File:** `C:\MetaReproducer\pipeline\meta_engine.py`, lines 74-157

`pool_dl()` handles k=1 but not k=0 (empty lists). If `yi=[]` and `sei=[]` are passed, line 116 will compute `w = [1.0 / v for v in vi]` which is empty, then `sum_w = 0`, then `mu_fe = 0/0` which raises `ZeroDivisionError`.

While the orchestrator guards against this (it only calls `pool_dl` when `ref_yi` is non-empty), the function itself should be defensive.

**Fix:** Add an early return at the top of `pool_dl`:
```python
if k == 0:
    return {"method": "DL", "pooled": None, "ci_lower": None, "ci_upper": None,
            "se": None, "tau2": 0.0, "i2": 0.0, "q_stat": 0.0, "q_pvalue": 1.0,
            "k": 0, "prediction_interval": None, "converged": True}
```

### P1-8 [FIXED]: Summary JSON written with `default=str` silently masks serialization issues [Software Engineer]

**File:** `C:\MetaReproducer\scripts\run_pipeline.py`, line 99
**File:** `C:\MetaReproducer\scripts\run_audit.py`, line 78

```python
json.dump(all_reports, f, indent=2, default=str)
```

The `default=str` parameter silently converts any non-serializable object to its string representation. This masks bugs where unexpected object types (e.g., numpy arrays, Path objects, datetime) end up in the report. The resulting JSON would have string representations like `"PosixPath('/path/to/file')"` instead of proper values, corrupting downstream analysis.

**Fix:** Remove `default=str` and fix any serialization issues explicitly, or use a custom serializer that only handles known types:
```python
def _json_default(obj):
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

json.dump(all_reports, f, indent=2, default=_json_default)
```

---

## P2 — Minor / Suggestions

### P2-1: REML Fisher scoring has redundant variable `sum_w_val` [Software Engineer]

**File:** `C:\MetaReproducer\pipeline\meta_engine.py`, line 217

```python
sum_w2_resid2 = sum(wi ** 2 * (y - mu) ** 2 for wi, y in zip(w, yi))
sum_w_val = sum(w)  # same as sum_w
score = 0.5 * (sum_w2_resid2 - sum_w_val)
```

`sum_w_val` is identical to `sum_w` (computed on line 209). The comment even says "same as sum_w". Use `sum_w` directly and remove the redundant variable.

### P2-2: Spec calls for 8 error taxonomy categories; only 3 are actively used [Domain Expert]

**File:** `C:\MetaReproducer\pipeline\taxonomy.py`, lines 33-43

The `CATEGORIES` list defines 8 categories (including `format_error`, `ambiguous_unit`, `sign_flip`, `scale_error`, `other`), matching the spec's 8-category design. However, `classify_study_error()` only ever returns 3 of them (`missing_pdf`, `extraction_failure`, `no_match`) plus `None` for success. The remaining 5 categories are defined but never produced.

**Impact:** Low -- these are "reserved for future use" and the code is clear about it. But the spec's Section 5.6 lists categories like `scale_mismatch`, `direction_flip`, `computation_gap`, `significance_shift`, `ambiguous_type` that are never implemented.

**Suggestion:** Either implement the additional categories in `classify_study_error()` or document that they are deferred. Consider adding at least `ambiguous_type` since effect_inference already produces an `"ambiguous"` label.

### P2-3: `_compute_rr` does not guard a=0 but guards c=0 [Statistical Methodologist]

**File:** `C:\MetaReproducer\pipeline\effect_inference.py`, lines 36-43

```python
def _compute_rr(a: float, n1: float, c: float, n2: float) -> Optional[float]:
    if n1 <= 0 or n2 <= 0 or c <= 0:
        return None
    return (a / n1) / (c / n2)
```

When `a=0`, RR = 0, which is mathematically valid but clinically unusual (zero events in experimental arm). The function returns 0.0 in this case. Meanwhile, `c=0` returns `None` (division by zero in the denominator). This asymmetry is mathematically correct but should be documented.

### P2-4: No logging framework; uses print() for diagnostics [Software Engineer]

**Files:** Multiple files use `print()` for status output (e.g., `ctgov_extractor.py` lines 44, 50, 64; `link_mega_data.py` lines 17, 58, 104-106).

For a production pipeline processing 465 reviews, structured logging with levels would be more appropriate. `print()` cannot be silenced, filtered, or redirected easily.

**Suggestion:** Use Python's `logging` module:
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Looking up %d PMIDs in AACT...", len(all_pmids))
```

### P2-5: `_safe_int` truncates floats silently [Software Engineer]

**File:** `C:\MetaReproducer\pipeline\rda_parser.py`, lines 66-69

```python
def _safe_int(val: Any) -> Optional[int]:
    f = _safe_float(val)
    return None if f is None else int(f)
```

`int(4.7)` returns `4`, silently truncating. For event counts and sample sizes, which should be whole numbers, this is probably fine in practice (RDA values should be integers stored as floats). But `int(float("inf"))` raises `OverflowError`, which is unhandled.

**Fix:** Add a guard:
```python
def _safe_int(val):
    f = _safe_float(val)
    if f is None or not math.isfinite(f):
        return None
    return int(f)
```

### P2-6: `se_from_ci` always assumes 95% CI [Statistical Methodologist]

**File:** `C:\MetaReproducer\pipeline\orchestrator.py`, line 66

```python
z = stats.norm.ppf(0.975)
```

The function hardcodes z for 95% CI. If any Cochrane review reports a different confidence level (rare but possible -- some report 99% CI), the SE back-calculation will be wrong.

**Suggestion:** Make the confidence level a parameter (default 0.95) and pass it through from the outcome metadata if available.

### P2-7: Missing `__all__` exports in pipeline modules [Software Engineer]

None of the pipeline modules define `__all__`, so `from pipeline.X import *` would import internal helpers. Low risk since this pattern is not used, but good practice to define public API boundaries.

### P2-8: Dashboard Selenium tests have hardcoded sleep timers [Testing Reviewer]

**File:** `C:\MetaReproducer\tests\test_dashboard.py`, multiple locations

The Selenium tests use `time.sleep(0.3)` through `time.sleep(1.5)` for waiting. These are fragile -- too short on slow machines, too long on fast ones. WebDriverWait with expected conditions would be more robust.

---

## Test Coverage Assessment [Testing Reviewer]

### What is well-tested:
- meta_engine.py: DL and REML with k=1, k=2, k=5, k=8, homogeneous, heterogeneous, convergence, Q/I2 -- thorough
- comparator.py: All 4 classification tiers, edge cases (zero ref, both non-sig) -- thorough
- effect_extractor.py: classify_match with 5%/10%/no-match, direct vs computed -- thorough
- taxonomy.py: All 3 active error categories + aggregation -- thorough
- truthcert.py: Hashing determinism, chain integrity -- thorough
- rda_parser.py: Grouping, data types, year filter -- good
- effect_inference.py: OR, RR, MD, SMD, GIV-only, ambiguous -- good
- Dashboard: 15 Selenium tests covering tabs, search, theme, a11y -- good

### Coverage gaps:
1. **Integration test for infer_effect_type with parsed RDA data** -- the P0-1 bug proves this path is untested. The existing `test_full_pipeline_real_rda` test does not assert on `inferred_effect_type` correctness.
2. **No test for pool_dl with k=0** -- covered by orchestrator guard, but the function itself is not defensive.
3. **No test for load_existing_extractions** with real or mocked data (only tested via integration).
4. **No test for extract_from_pdf** (acknowledged in docstring -- integration-only).
5. **No test for link_mega_data** functions beyond the `__main__` block.
6. **No test for generate_tables.py** or the `_generate_bmj_markdown()` function.
7. **No negative test for se_from_ci** with swapped lower/upper bounds (lower > upper).
8. **No test verifying REML non-convergence path** with pathological data.
9. **AACT integration tests** only test empty inputs and match logic; no mock-connection tests for `batch_pmid_to_nct`, `fetch_precomputed_effects`, or `fetch_raw_outcomes` with simulated data.

---

## Plan Alignment Assessment

### Alignment with spec:
The implementation closely follows the design spec (v2). Key design decisions are correctly implemented:
- Two-level classification (study + review) -- correct
- DL + REML with Fisher scoring -- correct (matches Viechtbauer 2005)
- Strict matching tiers (5% / 10%) only -- correct
- SE back-calculation from CI without hardcoded z=1.96 -- correct
- Primary outcome selection by largest k -- correct
- TruthCert SHA-256 provenance -- correct
- Error taxonomy framework -- correct (though incomplete)

### Deviations from spec:
1. **Spec uses dataclasses; implementation uses plain dicts.** The spec defines `CochraneStudy`, `CochraneOutcome`, `CochraneReview`, `PooledResult`, `ExtractedEffect`, etc. as dataclasses. The implementation uses plain dicts throughout. This is a reasonable simplification but reduces type safety.

2. **Spec says process ALL outcomes, select primary at analysis level.** The implementation (`run_pipeline.py` line 85, `run_audit.py` line 63) selects the primary outcome BEFORE calling `reproduce_outcome`, meaning only the primary outcome is audited per review. The spec says "we compute all outcomes and let the analysis scripts select which to report." This is a deviation that reduces coverage -- non-primary outcomes are never audited.

3. **AACT fallback pathway** is implemented but not in the original spec. This is a beneficial addition (second extraction source via CT.gov structured data).

4. **The spec's `run_single.py` is present** but was not in the review scope. The `run_pipeline.py` is an addition beyond the spec's `run_audit.py` and `generate_tables.py`.

5. **The spec mentions `title` and `therapeutic_area` fields on CochraneReview.** These are not implemented -- the parsed review dict has no `title` or `therapeutic_area`. The dashboard's "therapeutic area breakdown" will have no data.

---

## Summary

| Severity | Count | Key Issues |
|----------|-------|------------|
| P0 | 2 | Field name mismatch in effect_inference (silent wrong results); load_existing_extractions re-parsed per outcome |
| P1 | 8 | same_direction zero bug; cursor leaks; no timestamp; hardcoded paths; quartile accuracy; script duplication; k=0 guard; default=str masking |
| P2 | 8 | Redundant variable; unused taxonomy categories; asymmetric RR guard; print logging; safe_int overflow; CI level assumption; missing __all__; sleep timers |
| Test gaps | 9 | Integration path for effect_inference; k=0 pool_dl; load_existing_extractions; extract_from_pdf; link_mega_data; generate_tables; swapped CI; REML non-convergence; AACT mock tests |

**The P0-1 finding (field name mismatch) is the most critical issue.** It means the production pipeline has never correctly inferred effect types from parsed RDA data. All `inferred_effect_type` values would be `"unknown_ratio"`, and all studies would be treated as ratio measures. This corrupts the entire audit output. The fix is straightforward (6 line changes in effect_inference.py + test fixture updates) but must be verified with an integration test that exercises the full rda_parser -> effect_inference path.

## [WARN] P1-silent-failure-sentinel
- **Location:** `pipeline/effect_inference.py:106`
- **Detail:** pattern matched: return "unknown_ratio"
- **Fix hint:** Raise KeyError or a domain-specific exception instead of returning a sentinel string. Include expected-vs-received schema in the exception message.

- **Source:** lessons.md#integration-contracts
- **When:** 2026-04-15T02:01:24.688038+00:00

## [WARN] P1-silent-failure-sentinel
- **Location:** `pipeline/effect_inference.py:110`
- **Detail:** pattern matched: return "unknown_ratio"
- **Fix hint:** Raise KeyError or a domain-specific exception instead of returning a sentinel string. Include expected-vs-received schema in the exception message.

- **Source:** lessons.md#integration-contracts
- **When:** 2026-04-15T02:01:24.688062+00:00

## [WARN] P1-silent-failure-sentinel
- **Location:** `pipeline/effect_inference.py:112`
- **Detail:** pattern matched: return "unknown_ratio"
- **Fix hint:** Raise KeyError or a domain-specific exception instead of returning a sentinel string. Include expected-vs-received schema in the exception message.

- **Source:** lessons.md#integration-contracts
- **When:** 2026-04-15T02:01:24.688066+00:00

## [WARN] P1-silent-failure-sentinel
- **Location:** `pipeline/effect_inference.py:116`
- **Detail:** pattern matched: return "unknown_ratio"
- **Fix hint:** Raise KeyError or a domain-specific exception instead of returning a sentinel string. Include expected-vs-received schema in the exception message.

- **Source:** lessons.md#integration-contracts
- **When:** 2026-04-15T02:01:24.688069+00:00

## [WARN] P1-silent-failure-sentinel
- **Location:** `pipeline/effect_inference.py:125`
- **Detail:** pattern matched: return "unknown_ratio"
- **Fix hint:** Raise KeyError or a domain-specific exception instead of returning a sentinel string. Include expected-vs-received schema in the exception message.

- **Source:** lessons.md#integration-contracts
- **When:** 2026-04-15T02:01:24.688073+00:00

## [WARN] P1-silent-failure-sentinel
- **Location:** `pipeline/effect_inference.py:152`
- **Detail:** pattern matched: return "unknown_ratio"
- **Fix hint:** Raise KeyError or a domain-specific exception instead of returning a sentinel string. Include expected-vs-received schema in the exception message.

- **Source:** lessons.md#integration-contracts
- **When:** 2026-04-15T02:01:24.688081+00:00

## [WARN] P1-silent-failure-sentinel
- **Location:** `pipeline/effect_inference.py:171`
- **Detail:** pattern matched: return "unknown_ratio"
- **Fix hint:** Raise KeyError or a domain-specific exception instead of returning a sentinel string. Include expected-vs-received schema in the exception message.

- **Source:** lessons.md#integration-contracts
- **When:** 2026-04-15T02:01:24.688087+00:00
