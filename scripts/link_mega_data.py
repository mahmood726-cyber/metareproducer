#!/usr/bin/env python
# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""Link Pairwise70 RDA studies to existing mega gold standard PDFs."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.paths import (
    resolve_mega_matched_path,
    resolve_mega_pdf_dir,
    resolve_pairwise_rda_dir,
)


def build_study_pdf_map() -> dict:
    """Build mapping: (first_author, year) -> pdf_path from mega_matched.jsonl."""
    matched_path = resolve_mega_matched_path(required=False)
    if matched_path is None:
        print("WARNING: mega_matched.jsonl not found")
        return {}
    # Build index of actual PDF files on disk: pmcid -> path
    pdf_by_pmcid = {}
    pdf_dir = resolve_mega_pdf_dir(required=False)
    if pdf_dir is not None and pdf_dir.exists():
        for pdf in pdf_dir.glob("*.pdf"):
            # Filename format: Author_Year_Year_PMCID.pdf
            parts = pdf.stem.split("_")
            # PMCID is the last part (PMCxxxxxxx)
            for part in reversed(parts):
                if part.startswith("PMC"):
                    pdf_by_pmcid[part] = str(pdf)
                    break

    mapping = {}
    with open(matched_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            pmcid = entry.get("pmcid")
            if not pmcid:
                continue
            pdf_path = pdf_by_pmcid.get(pmcid)
            if not pdf_path:
                continue
            author = entry.get("first_author", "")
            year = entry.get("year")
            key = (author.strip(), year)
            mapping[key] = pdf_path
    return mapping


def build_study_pmid_map() -> dict:
    """Build mapping: (first_author, year) -> pmid from mega_matched.jsonl.

    Returns {(author_str, year_int): pmid_str} for all entries with a PMID.
    """
    matched_path = resolve_mega_matched_path(required=False)
    if matched_path is None:
        print("WARNING: mega_matched.jsonl not found")
        return {}

    mapping = {}
    with open(matched_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            pmid = entry.get("pmid")
            if not pmid:
                continue
            author = entry.get("first_author", "")
            year = entry.get("year")
            key = (author.strip(), year)
            mapping[key] = str(pmid)
    return mapping


def link_reviews(reviews: list[dict], pdf_map: dict,
                  pmid_map: dict | None = None) -> None:
    """Mutate reviews in-place: set pdf_path and pmid on matching studies.

    Parameters
    ----------
    reviews  : list of review dicts (each with outcomes -> studies)
    pdf_map  : {(author, year): pdf_path}
    pmid_map : {(author, year): pmid} — optional; built by build_study_pmid_map()
    """
    linked = 0
    pmid_linked = 0
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
                if pmid_map and key in pmid_map:
                    study["pmid"] = pmid_map[key]
                    pmid_linked += 1
    print(f"Linked {linked}/{total} studies to PDFs ({100*linked/max(total,1):.1f}%)")
    if pmid_map is not None:
        print(f"Linked {pmid_linked}/{total} studies to PMIDs ({100*pmid_linked/max(total,1):.1f}%)")


if __name__ == "__main__":
    from pipeline.rda_parser import load_all_rdas
    rda_dir = resolve_pairwise_rda_dir(required=True)
    reviews = load_all_rdas(rda_dir)
    pdf_map = build_study_pdf_map()
    link_reviews(reviews, pdf_map)
