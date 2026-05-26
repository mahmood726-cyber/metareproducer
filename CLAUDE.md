<!-- sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files. -->

# MetaReproducer

## Purpose
Automated reproducibility audit of 465 Cochrane meta-analyses.
Pipeline re-extracts effects from trial PDFs, re-pools, compares against Cochrane reference.

## Key paths
- Pairwise70 RDA dir: auto-discovered, or set `METAREPRODUCER_RDA_DIR`
- RCT Extractor checkout: auto-discovered, or set `METAREPRODUCER_RCT_EXTRACTOR_DIR`
- Mega gold data dir: auto-discovered, or set `METAREPRODUCER_MEGA_DIR`
- CT.gov credentials file: auto-discovered, or set `METAREPRODUCER_CTGOV_ENV`

## Rules
- Use `python` not `python3` (Windows)
- No hardcoded z=1.96 — use scipy.stats.norm.ppf
- No LLM extraction — deterministic only
- Test-first: run tests after every change
