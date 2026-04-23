#!/usr/bin/env python
# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""Unified MetaReproducer pipeline: link → audit → tables → validate.

Usage:
    python scripts/run_pipeline.py              # full pipeline
    python scripts/run_pipeline.py --skip-aact  # skip CT.gov AACT lookup
    python scripts/run_pipeline.py --tables-only # regenerate tables from existing summary.json
"""
import sys
import json
import argparse
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.rda_parser import load_all_rdas
from pipeline import effect_extractor
from pipeline.effect_inference import infer_outcome_types
from pipeline.orchestrator import reproduce_review
from link_mega_data import build_study_pdf_map, build_study_pmid_map, link_reviews

RDA_DIR = Path(r"C:\Users\user\OneDrive - NHS\Documents\Pairwise70\data")
RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"


def _primary_reports(reports):
    """Return one primary outcome report per review when available."""
    primary = [r for r in reports if r.get("is_primary") is True]
    return primary if primary else reports


def _write_summary_files(reports):
    """Persist both full outcome-level and primary-outcome summaries."""
    def _json_default(obj):
        import numpy as _np
        from pathlib import Path as _Path
        if isinstance(obj, _Path):
            return str(obj)
        if isinstance(obj, (_np.bool_, )):
            return bool(obj)
        if isinstance(obj, (_np.integer, )):
            return int(obj)
        if isinstance(obj, (_np.floating, )):
            return float(obj)
        if isinstance(obj, _np.ndarray):
            return obj.tolist()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    summary_path = RESULTS_DIR / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(reports, f, indent=2, default=_json_default)

    primary_path = RESULTS_DIR / "summary_primary.json"
    with open(primary_path, "w") as f:
        json.dump(_primary_reports(reports), f, indent=2, default=_json_default)


def phase_1_load_and_link():
    """Load all RDA files and link studies to PDFs + PMIDs."""
    print("\n" + "=" * 60)
    print("PHASE 1: Load RDA files and link to PDFs/PMIDs")
    print("=" * 60)
    t0 = time.time()

    reviews = load_all_rdas(RDA_DIR)
    print(f"Loaded {len(reviews)} reviews from Pairwise70")

    pdf_map = build_study_pdf_map()
    pmid_map = build_study_pmid_map()
    link_reviews(reviews, pdf_map, pmid_map)

    elapsed = time.time() - t0
    print(f"Phase 1 complete in {elapsed:.1f}s")
    return reviews


def phase_2_audit(reviews, skip_aact=False):
    """Run reproducibility audit on all reviews."""
    print("\n" + "=" * 60)
    print("PHASE 2: Reproducibility audit")
    print("=" * 60)
    t0 = time.time()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    # Optional AACT lookup (tries PostgreSQL first, falls back to REST API v2)
    aact_lookup = None
    if not skip_aact:
        all_pmids = set()
        for review in reviews:
            for outcome in review["outcomes"]:
                for study in outcome["studies"]:
                    pmid = study.get("pmid")
                    if pmid:
                        all_pmids.add(str(pmid))
        all_pmids = list(all_pmids)

        # Strategy 1: AACT PostgreSQL (requires credentials)
        try:
            from pipeline.ctgov_extractor import get_connection, build_aact_lookup
            conn = get_connection()
            if conn:
                print(f"Looking up {len(all_pmids)} PMIDs in AACT PostgreSQL...")
                aact_lookup = build_aact_lookup(conn, all_pmids)
                print(f"AACT PostgreSQL: {len(aact_lookup)} studies with CT.gov data")
                conn.close()
        except Exception as e:
            print(f"AACT PostgreSQL unavailable ({e})")

        # Strategy 2: CT.gov REST API v2 fallback (no credentials needed)
        if aact_lookup is None:
            try:
                from pipeline.ctgov_extractor import build_aact_lookup_via_api
                print(f"\nFalling back to CT.gov REST API v2 (no auth required)...")
                print(f"Looking up {len(all_pmids)} unique PMIDs...")
                aact_lookup = build_aact_lookup_via_api(all_pmids)
                print(f"CT.gov API v2: {len(aact_lookup)} studies with effect data")
            except Exception as e:
                print(f"CT.gov API v2 also unavailable ({e}) -- PDF pathway only")

    try:
        existing_extractions = effect_extractor.load_existing_extractions()
    except FileNotFoundError:
        existing_extractions = {}
    all_reports = []
    n_errors = 0
    for i, review in enumerate(reviews):
        for outcome in review["outcomes"]:
            infer_outcome_types(outcome)

        if not review["outcomes"]:
            continue

        try:
            reports = reproduce_review(
                review["review_id"],
                review["outcomes"],
                aact_lookup=aact_lookup,
                existing_extractions=existing_extractions,
            )
            all_reports.extend(reports)
        except Exception as e:
            print(f"  ERROR: {review['review_id']}: {e}")
            n_errors += 1

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(reviews)}]", flush=True)

    _write_summary_files(all_reports)
    n_primary = len(_primary_reports(all_reports))

    elapsed = time.time() - t0
    print(f"\nPhase 2 complete in {elapsed:.1f}s")
    print(f"  {n_primary} reviews audited, {len(all_reports)} outcomes saved, {n_errors} errors")
    return all_reports


def phase_3_tables(reports=None):
    """Generate BMJ manuscript tables from audit results."""
    print("\n" + "=" * 60)
    print("PHASE 3: Generate BMJ manuscript tables")
    print("=" * 60)

    if reports is None:
        summary_path = RESULTS_DIR / "summary.json"
        if not summary_path.exists():
            print("ERROR: summary.json not found. Run audit first.")
            return
        with open(summary_path) as f:
            reports = json.load(f)

    from generate_tables import main as generate_main
    generate_main()

    # Also generate the enhanced markdown tables
    _generate_bmj_markdown(reports)


def _generate_bmj_markdown(reports):
    """Generate BMJ-formatted markdown tables + figure data."""
    from collections import Counter

    md_path = RESULTS_DIR / "bmj_tables.md"
    fig_path = RESULTS_DIR / "figure_data.json"
    primary_reports = _primary_reports(reports)

    # ---- Table 1: Review characteristics ----
    total_k_values = [r["study_level"]["total_k"] for r in primary_reports]
    n_with_pdf_values = [r["study_level"]["n_with_pdf"] for r in primary_reports]
    effect_types = Counter(r.get("inferred_effect_type", "unknown") for r in primary_reports)

    lines = []
    lines.append("# MetaReproducer: BMJ Manuscript Tables")
    lines.append("")
    lines.append("## Table 1. Characteristics of included Cochrane reviews (primary outcome per review)")
    lines.append("")
    lines.append(f"| Characteristic | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Reviews included | {len(primary_reports)} |")
    lines.append(f"| Total study outcomes | {sum(total_k_values)} |")
    lines.append(f"| Median studies per review (IQR) | {_median(total_k_values)} ({_q1(total_k_values)}-{_q3(total_k_values)}) |")
    lines.append(f"| Studies with PDF available | {sum(n_with_pdf_values)} ({100*sum(n_with_pdf_values)/max(sum(total_k_values),1):.1f}%) |")
    for et in sorted(effect_types):
        lines.append(f"| Effect type: {et} | {effect_types[et]} ({100*effect_types[et]/max(len(primary_reports),1):.1f}%) |")
    lines.append("")

    # ---- Table 2: Study-level reproducibility ----
    by_type = {}
    for r in primary_reports:
        et = r.get("inferred_effect_type", "unknown")
        if et not in by_type:
            by_type[et] = {"n_pdf": 0, "strict": 0, "moderate": 0, "reviews": 0}
        by_type[et]["n_pdf"] += r["study_level"]["n_with_pdf"]
        by_type[et]["strict"] += r["study_level"]["matched_strict"]
        by_type[et]["moderate"] += r["study_level"]["matched_moderate"]
        by_type[et]["reviews"] += 1

    lines.append("## Table 2. Study-level reproducibility by effect type (primary outcome per review)")
    lines.append("")
    lines.append("| Effect type | Reviews | Studies with PDF | Strict match (<=5%) | Moderate match (<=10%) |")
    lines.append("|---|---|---|---|---|")
    grand_pdf = grand_strict = grand_mod = 0
    for et in sorted(by_type):
        d = by_type[et]
        n = d["n_pdf"]
        grand_pdf += n
        grand_strict += d["strict"]
        grand_mod += d["moderate"]
        s_pct = f'{100*d["strict"]/max(n,1):.1f}%' if n > 0 else "N/A"
        m_pct = f'{100*d["moderate"]/max(n,1):.1f}%' if n > 0 else "N/A"
        lines.append(f"| {et} | {d['reviews']} | {n} | {d['strict']} ({s_pct}) | {d['moderate']} ({m_pct}) |")
    s_pct = f'{100*grand_strict/max(grand_pdf,1):.1f}%' if grand_pdf > 0 else "N/A"
    m_pct = f'{100*grand_mod/max(grand_pdf,1):.1f}%' if grand_pdf > 0 else "N/A"
    lines.append(f"| **Total** | **{len(primary_reports)}** | **{grand_pdf}** | **{grand_strict} ({s_pct})** | **{grand_mod} ({m_pct})** |")
    lines.append("")

    # ---- Table 3: Review-level classification ----
    classified = [r for r in primary_reports if r["review_level"] is not None]
    tiers = Counter(r["review_level"]["classification"] for r in classified)
    insufficient = len(primary_reports) - len(classified)

    lines.append("## Table 3. Review-level reproducibility classification (primary outcome per review)")
    lines.append("")
    lines.append("| Classification | n | % |")
    lines.append("|---|---|---|")
    for tier_name in ["reproduced", "minor_discrepancy", "major_discrepancy"]:
        n = tiers.get(tier_name, 0)
        lines.append(f"| {tier_name.replace('_', ' ').title()} | {n} | {100*n/max(len(primary_reports),1):.1f}% |")
    lines.append(f"| Insufficient coverage | {insufficient} | {100*insufficient/max(len(primary_reports),1):.1f}% |")
    lines.append(f"| **Total** | **{len(primary_reports)}** | **100.0%** |")
    lines.append("")

    # ---- Table 4: Error taxonomy ----
    error_totals = Counter()
    for r in reports:
        for cat, count in r["errors"].items():
            if cat != "primary_error_source" and isinstance(count, int):
                error_totals[cat] += count

    lines.append("## Table 4. Error taxonomy across all study outcomes")
    lines.append("")
    lines.append("| Error category | n | % of total |")
    lines.append("|---|---|---|")
    grand_total = sum(error_totals.values())
    for cat, count in error_totals.most_common():
        lines.append(f"| {cat.replace('_', ' ').title()} | {count} | {100*count/max(grand_total,1):.1f}% |")
    lines.append(f"| **Total** | **{grand_total}** | **100.0%** |")
    lines.append("")

    # ---- Table 5: Discrepant reviews detail ----
    discrepant = [r for r in classified
                  if r["review_level"]["classification"] in ("minor_discrepancy", "major_discrepancy")]
    if discrepant:
        lines.append("## Table 5. Reviews with discrepant reproducibility results (primary outcome per review)")
        lines.append("")
        lines.append("| Review ID | Effect type | k | k_extracted | Classification | Ref pooled | Repro pooled | Rel. diff |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in sorted(discrepant, key=lambda x: x["review_id"]):
            rl = r["review_level"]
            ref_p = r.get("reference_pooled", {}).get("pooled", "")
            rep_p = r.get("reproduced_pooled", {}).get("pooled", "")
            ref_str = f"{ref_p:.4f}" if isinstance(ref_p, float) else str(ref_p)
            rep_str = f"{rep_p:.4f}" if isinstance(rep_p, float) else str(rep_p)
            rel = rl.get("rel_diff")
            rel_str = f"{100*rel:.1f}%" if rel is not None else "N/A"
            lines.append(f"| {r['review_id']} | {r.get('inferred_effect_type', '?')} | "
                         f"{r['study_level']['total_k']} | {rl.get('reproduced_k', 'N/A')} | "
                         f"{rl['classification'].replace('_', ' ')} | {ref_str} | {rep_str} | {rel_str} |")
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  BMJ markdown tables saved: {md_path}")

    # ---- Figure data: Sankey + Waterfall ----
    fig_data = {
        "sankey": {
            "description": "Flow from total studies through extraction to classification",
            "nodes": ["All studies", "With PDF", "Extracted", "Strict match",
                       "Moderate match", "No match", "No PDF"],
            "flows": [
                {"from": "All studies", "to": "With PDF", "value": grand_pdf},
                {"from": "All studies", "to": "No PDF",
                 "value": sum(total_k_values) - grand_pdf},
                {"from": "With PDF", "to": "Strict match", "value": grand_strict},
                {"from": "With PDF", "to": "Moderate match",
                 "value": grand_mod - grand_strict},
                {"from": "With PDF", "to": "No match",
                 "value": grand_pdf - grand_mod},
            ],
        },
        "waterfall": {
            "description": "Review-level classification waterfall",
            "categories": ["Reproduced", "Minor discrepancy",
                            "Major discrepancy", "Insufficient"],
            "counts": [
                tiers.get("reproduced", 0),
                tiers.get("minor_discrepancy", 0),
                tiers.get("major_discrepancy", 0),
                insufficient,
            ],
        },
        "heterogeneity_distribution": {
            "description": "Distribution of I-squared across reviews with reference pooled",
            "i2_values": [
                r["reference_pooled"]["i2"]
                for r in primary_reports
                if r.get("reference_pooled") and "i2" in r["reference_pooled"]
            ],
        },
    }

    with open(fig_path, "w") as f:
        json.dump(fig_data, f, indent=2)
    print(f"  Figure data saved: {fig_path}")


def _median(vals):
    if not vals:
        return 0
    s = sorted(vals)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def _q1(vals):
    if not vals:
        return 0
    import numpy as np
    return float(np.percentile(vals, 25))


def _q3(vals):
    if not vals:
        return 0
    import numpy as np
    return float(np.percentile(vals, 75))


def main():
    parser = argparse.ArgumentParser(description="MetaReproducer unified pipeline")
    parser.add_argument("--skip-aact", action="store_true",
                        help="Skip AACT/CT.gov lookup")
    parser.add_argument("--tables-only", action="store_true",
                        help="Only regenerate tables from existing summary.json")
    args = parser.parse_args()

    if args.tables_only:
        phase_3_tables()
        return

    reviews = phase_1_load_and_link()
    reports = phase_2_audit(reviews, skip_aact=args.skip_aact)
    phase_3_tables(reports)

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
