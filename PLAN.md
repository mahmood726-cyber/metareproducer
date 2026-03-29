# MetaReproducer — Development Plan

## Vision
BMJ-targeted automated reproducibility audit of 465 Cochrane meta-analyses. Python pipeline re-extracts effects from trial PDFs, re-pools via DerSimonian-Laird and REML, and classifies reproducibility at study and review levels with full TruthCert provenance.

---

## Phase 1: Core Pipeline (DONE)
- 9 Python modules: PDF extraction, effect size computation, pooling engine, concordance classifier, TruthCert bundler, BMJ table generator, dashboard renderer, batch orchestrator, validation harness
- 87 tests passing
- Two-level reproducibility classification:
  - **Study-level**: ~1,290 PDFs, ~24% strict match (effect size within 1% tolerance)
  - **Review-level**: ~80-120 assessable reviews (concordance of direction + significance + heterogeneity)
- BMJ-format summary tables (Table 1: review characteristics, Table 2: reproducibility rates, Table 3: discrepancy taxonomy)
- TruthCert provenance chain: PDF hash -> extracted values -> pooled result -> concordance verdict
- Interactive HTML dashboard with drill-down per review

---

## Phase 2: All-Outcome Processing + Validation (NEXT)

### 2A. All-Outcome Expansion
- Currently processes primary outcome only; extend to ALL reported outcomes per review
- Parse Cochrane RevMan XML for complete outcome tree (primary, secondary, subgroup, sensitivity)
- Map extracted PDF effects to specific outcomes (not just first-reported)
- Expected yield: 3-5x more study-level comparisons (from ~1,290 to ~4,000-6,000)
- Handle multi-arm trials: pairwise decomposition with shared-arm correlation adjustment

### 2B. Therapeutic Area Classification
- Auto-classify reviews into ICD-11 chapters (cardiovascular, oncology, infectious disease, etc.)
- Use Cochrane Review Group metadata + MeSH terms from included trials
- Enable stratified reproducibility reporting: "reproducibility rates by therapeutic area"
- Hypothesis: pharmacological interventions more reproducible than behavioral/complex interventions

### 2C. Interactive Dashboard Enhancement
- Add filtering by: therapeutic area, review year, number of included studies, effect measure type
- Reproducibility trend over time (are newer reviews more reproducible?)
- Funnel plot of reproducibility: do larger reviews have higher concordance?
- Downloadable CSV of all study-level and review-level results

### 2D. R Validation Suite
- Cross-validate JS pooling engine against metafor (DL, REML, PM, HKSJ)
- Validate heterogeneity estimates (tau2, I2, H2, prediction intervals)
- Tolerance: 1e-6 for point estimates, 1e-4 for CI bounds
- Automated R script generation for each review (reproducible in R without the tool)
- Target: 100% parity on 50 randomly sampled reviews

### 2E. Manuscript Preparation
- BMJ Research Article format (3,000-word limit)
- STROBE-like reporting for reproducibility studies
- Pre-registration on OSF (analysis plan + primary/secondary outcomes)
- Figures: reproducibility waterfall plot, therapeutic area heatmap, trend over time
- Supplementary: full review-level results table, R validation report, TruthCert bundle

**Phase 2 Target**: ~4,000-6,000 study-level comparisons, R-validated, manuscript draft complete

---

## Phase 3: Living Observatory + Submission

### 3A. Living Observatory Mode
- Monitor CT.gov for new trial results in reviews with low reproducibility
- Alert when new evidence could change a non-reproducible review's conclusion
- Quarterly re-run of pipeline on updated Cochrane Library exports
- Version-controlled reproducibility snapshots (track changes over time)

### 3B. Zenodo Deposit
- Archive: pipeline code, extracted data (no copyrighted PDFs), pooled results, TruthCert bundles
- DOI for citation in manuscript
- Reproducibility capsule: Docker container with pinned dependencies

### 3C. BMJ Submission
- Target: BMJ Research Article or BMJ Open
- Cover letter emphasizing: first automated large-scale reproducibility audit, actionable findings, open-source tool
- Reviewer-friendly package: Zenodo capsule + interactive dashboard URL + R validation report

**Phase 3 Target**: Living observatory operational, Zenodo DOI minted, BMJ submission

---

## Success Criteria
- [ ] All-outcome processing yields 4,000+ study-level comparisons
- [ ] Therapeutic area classification covers 90%+ of reviews
- [ ] R validation: 100% parity on 50 sampled reviews (tolerance 1e-6)
- [ ] Dashboard filters functional with <500ms response
- [ ] BMJ manuscript draft complete with all figures and tables
- [ ] Zenodo deposit with DOI
- [ ] Living observatory detects at least 1 reproducibility change in quarterly re-run
