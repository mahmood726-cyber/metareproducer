#!/usr/bin/env python
"""Generate BMJ manuscript tables from audit results."""
import sys
import json
import csv
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"


def _primary_reports(reports):
    primary = [r for r in reports if r.get("is_primary") is True]
    return primary if primary else reports


def _review_tier(report):
    rl = report.get("review_level") or {}
    return rl.get("classification", rl.get("tier", "insufficient"))


def _pct_difference(report):
    rl = report.get("review_level") or {}
    return rl.get("rel_diff", rl.get("pct_difference"))


def write_summary_tables(reports, results_dir=RESULTS_DIR):
    """Write primary-only and all-outcome CSV summaries for a report set."""
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    primary_reports = _primary_reports(reports)

    csv_path = results_dir / "summary_table.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["review_id", "outcome", "effect_type", "total_k",
                          "n_with_pdf", "matched_strict", "matched_moderate",
                          "review_tier", "ref_pooled", "repro_pooled", "pct_diff"])
        for r in primary_reports:
            ref_p = r.get("reference_pooled") or {}
            rep_p = r.get("reproduced_pooled") or {}
            writer.writerow([
                r["review_id"], r["outcome_label"], r.get("inferred_effect_type"),
                r["study_level"]["total_k"], r["study_level"]["n_with_pdf"],
                r["study_level"]["matched_strict"], r["study_level"]["matched_moderate"],
                _review_tier(r),
                ref_p.get("pooled"), rep_p.get("pooled"),
                _pct_difference(r),
            ])

    all_csv_path = results_dir / "summary_table_all_outcomes.csv"
    with open(all_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["review_id", "outcome", "is_primary", "outcome_rank", "effect_type", "total_k",
                         "n_with_pdf", "matched_strict", "matched_moderate",
                         "review_tier", "ref_pooled", "repro_pooled", "pct_diff"])
        for r in reports:
            ref_p = r.get("reference_pooled") or {}
            rep_p = r.get("reproduced_pooled") or {}
            writer.writerow([
                r["review_id"], r["outcome_label"], r.get("is_primary", ""),
                r.get("outcome_rank", ""), r.get("inferred_effect_type"),
                r["study_level"]["total_k"], r["study_level"]["n_with_pdf"],
                r["study_level"]["matched_strict"], r["study_level"]["matched_moderate"],
                _review_tier(r),
                ref_p.get("pooled"), rep_p.get("pooled"),
                _pct_difference(r),
            ])

    return {
        "primary_csv": csv_path,
        "all_outcomes_csv": all_csv_path,
        "primary_reports": primary_reports,
    }


def main():
    summary_path = RESULTS_DIR / "summary.json"
    if not summary_path.exists():
        print("Run run_audit.py first to generate results.")
        sys.exit(1)

    with open(summary_path) as f:
        reports = json.load(f)
    primary_reports = _primary_reports(reports)

    print(f"\n=== Table 1: Study-level by effect type (primary outcome per review) ===")
    by_type = {}
    for r in primary_reports:
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

    print(f"\n=== Table 2: Review-level classification (primary outcome per review) ===")
    classified = [r for r in primary_reports if r["review_level"] is not None]
    tiers = Counter(r["review_level"]["classification"] for r in classified)
    insufficient = sum(1 for r in primary_reports if r["review_level"] is None)
    print(f"  Reproduced: {tiers.get('reproduced', 0)}")
    print(f"  Minor discrepancy: {tiers.get('minor_discrepancy', 0)}")
    print(f"  Major discrepancy: {tiers.get('major_discrepancy', 0)}")
    print(f"  Insufficient coverage: {insufficient}")

    print(f"\n=== Table 3: Error taxonomy ===")
    error_totals = Counter()
    for r in reports:
        for k, v in r["errors"].items():
            if k not in ("primary_error_source",) and isinstance(v, int):
                error_totals[k] += v
    for cat, count in error_totals.most_common():
        print(f"  {cat}: {count}")

    outputs = write_summary_tables(reports, results_dir=RESULTS_DIR)
    print(f"\nCSV saved: {outputs['primary_csv']}")
    print(f"All-outcomes CSV saved: {outputs['all_outcomes_csv']}")


if __name__ == "__main__":
    main()
