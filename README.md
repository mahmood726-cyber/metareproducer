# Computational Reproducibility Audit of 501 Cochrane Meta-Analyses

[![ci](https://github.com/mahmood726-cyber/metareproducer/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/mahmood726-cyber/metareproducer/actions/workflows/ci.yml) [![codeql](https://github.com/mahmood726-cyber/metareproducer/actions/workflows/codeql.yml/badge.svg?branch=master)](https://github.com/mahmood726-cyber/metareproducer/actions/workflows/codeql.yml) [![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

Can Cochrane meta-analyses be computationally reproduced when an automated pipeline re-extracts effect sizes from source trial publications? We audited 501 Cochrane systematic reviews encompassing 14,340 individual studies using MetaReproducer, a deterministic pipeline that parses RevMan data files, retrieves open-access PDFs, extracts effects via RCT Extractor v10.3, and re-pools results using inverse-variance random-effects models. The pipeline infers effect type by back-computing candidate log-odds and log-risk ratios from two-by-two tables, matching against Cochrane reference values within 0.0001 tolerance on the log scale. Only 1,688 of 14,340 studies had accessible PDFs, yielding an open-access prevalence of 11.8 percent (95% CI 11.3-12.3), leaving most evidence computationally unverifiable. Among six reviews with sufficient coverage for classification, two showed major discrepancies including one complete direction change. The primary barrier to reproducibility is infrastructural access rather than methodology, suggesting that mandating structured data deposition could transform verification. This fundamental limitation of open-access coverage constrains any automated reproducibility audit of the published evidence base.

**Live dashboard:** <https://mahmood726-cyber.github.io/metareproducer/>

## Run

Open `index.html` (or `index.html`) in any modern browser. No build step.

For local development:

```bash
python -m http.server 8000
# then open http://localhost:8000/
```

## Test

```bash
python -m pytest -q
```

The suite under `tests/` includes 12 test file(s).

## Repo layout

| Path | Purpose |
|---|---|
| `index.html` | the dashboard (main artifact) |
| `index.html` | landing page |
| `tests/` | pytest tests |
| `e156-submission/` | E156 micro-paper bundle |
| `E156-PROTOCOL.md` | project metadata (E156 entry #106) |

## License

See `LICENSE` (MIT).
