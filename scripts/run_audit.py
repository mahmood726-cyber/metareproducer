#!/usr/bin/env python
# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""Run MetaReproducer audit on all Pairwise70 reviews."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rda_parser import load_all_rdas
from pipeline import effect_extractor
from pipeline.effect_inference import infer_outcome_types
from pipeline.orchestrator import reproduce_review

# Also import the linking module
sys.path.insert(0, str(Path(__file__).parent))
from link_mega_data import build_study_pdf_map, build_study_pmid_map, link_reviews

RDA_DIR = Path(r"C:\Users\user\OneDrive - NHS\Documents\Pairwise70\data")
RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"


def _primary_reports(reports):
    primary = [r for r in reports if r.get("is_primary") is True]
    return primary if primary else reports


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading all RDA files...")
    reviews = load_all_rdas(RDA_DIR)
    print(f"Loaded {len(reviews)} reviews")

    # Link studies to existing PDFs and PMIDs from mega gold standard
    print("Linking studies to PDFs and PMIDs...")
    pdf_map = build_study_pdf_map()
    pmid_map = build_study_pmid_map()
    link_reviews(reviews, pdf_map, pmid_map)

    aact_lookup = None
    # Initialize AACT CT.gov lookup (second extraction pathway)
    all_pmids = []
    for review in reviews:
        for outcome in review["outcomes"]:
            for study in outcome["studies"]:
                pmid = study.get("pmid")
                if pmid:
                    all_pmids.append(str(pmid))
    all_pmids = list(set(all_pmids))

    try:
        from pipeline.ctgov_extractor import get_connection, build_aact_lookup
        conn = get_connection()
        if conn:
            print(f"Looking up {len(all_pmids)} PMIDs in AACT...")
            aact_lookup = build_aact_lookup(conn, all_pmids)
            print(f"AACT lookup: {len(aact_lookup)} studies with CT.gov data")
            conn.close()
    except Exception as e:
        print(f"AACT PostgreSQL unavailable ({e})")

    if aact_lookup is None:
        try:
            from pipeline.ctgov_extractor import build_aact_lookup_via_api
            print("Falling back to CT.gov REST API v2...")
            print(f"Looking up {len(all_pmids)} unique PMIDs...")
            aact_lookup = build_aact_lookup_via_api(all_pmids)
            print(f"CT.gov API v2: {len(aact_lookup)} studies with effect data")
        except Exception as e:
            print(f"CT.gov API v2 unavailable ({e}) — using PDF pathway only")

    try:
        existing_extractions = effect_extractor.load_existing_extractions()
    except FileNotFoundError:
        existing_extractions = {}
    all_reports = []
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
            continue

        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(reviews)}] Last: {review['review_id']}", flush=True)

    summary_path = RESULTS_DIR / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(all_reports, f, indent=2, default=str)
    primary_reports = _primary_reports(all_reports)
    primary_path = RESULTS_DIR / "summary_primary.json"
    with open(primary_path, "w") as f:
        json.dump(primary_reports, f, indent=2, default=str)
    print(f"\nSaved {len(all_reports)} outcome reports to {summary_path}")
    print(f"Saved {len(primary_reports)} primary outcome reports to {primary_path}")

    # Headline stats
    study_total = sum(r["study_level"]["total_k"] for r in primary_reports)
    study_matched = sum(r["study_level"]["matched_moderate"] for r in primary_reports)
    review_classified = [r for r in primary_reports if r["review_level"] is not None]
    reproduced = sum(1 for r in review_classified if r["review_level"]["classification"] == "reproduced")
    major = sum(1 for r in review_classified if r["review_level"]["classification"] == "major_discrepancy")

    print(f"\n=== HEADLINE RESULTS ===")
    print(f"Reviews processed: {len(primary_reports)}")
    print(f"Outcomes audited: {len(all_reports)}")
    print(f"Study-level: {study_matched}/{study_total} matched within 10%")
    print(f"Review-level classified: {len(review_classified)}")
    print(f"  Reproduced: {reproduced}")
    print(f"  Major discrepancy: {major}")


if __name__ == "__main__":
    main()
