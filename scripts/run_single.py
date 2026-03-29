#!/usr/bin/env python
"""Run MetaReproducer on a single RDA file for debugging."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.rda_parser import load_rda
from pipeline.effect_inference import infer_outcome_types
from pipeline.orchestrator import reproduce_review


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

    if not review["outcomes"]:
        print("No outcomes found.")
        return

    reports = reproduce_review(review["review_id"], review["outcomes"])
    for report in reports:
        marker = " [PRIMARY]" if report.get("is_primary") else ""
        print(f"\nOutcome: {report['outcome_label']}{marker}")
        print(f"Study-level: {report['study_level']}")
        print(f"Review-level: {report['review_level']}")
        print(f"Errors: {report['errors']}")

    out_path = Path("data/results") / f"{review['review_id']}_reports.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(reports, f, indent=2, default=str)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
