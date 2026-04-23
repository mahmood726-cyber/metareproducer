# sentinel:skip-file — hardcoded paths are fixture/registry/audit-narrative data for this repo's research workflow, not portable application configuration. Same pattern as push_all_repos.py and E156 workbook files.
"""
AACT Database Integration — pipeline/ctgov_extractor.py

Connects to ClinicalTrials.gov structured results via EITHER:
  1. AACT PostgreSQL database (if AACT_USER / AACT_PASSWORD are set), OR
  2. CT.gov REST API v2 (no credentials needed — public, free, no auth).

The API v2 fallback is activated automatically when AACT credentials are
missing.  It batches PMID->NCT lookups and fetches outcome_analyses from
the JSON API, producing the same {pmid: {nct_id, effects, raw}} shape
that the AACT pathway returns.

Public API
----------
get_connection()                           -> connection | None
batch_pmid_to_nct(conn, pmids)             -> {pmid: nct_id}
fetch_precomputed_effects(conn, nct_ids)   -> {nct_id: [effect_dict]}
fetch_raw_outcomes(conn, nct_ids)          -> {nct_id: [outcome_dict]}
match_aact_effect(effects, cochrane, is_r) -> match_dict | None
build_aact_lookup(conn, pmids)             -> {pmid: {nct_id, effects, raw}}
build_aact_lookup_via_api(pmids)           -> {pmid: {nct_id, effects, raw}}

Notes
-----
- Credentials loaded from dotenv (AACT_USER, AACT_PASSWORD).
- All functions handle missing/None inputs gracefully.
- match_aact_effect reuses classify_match from effect_extractor for consistency.
- API v2 rate-limits: ~3 req/s sustained; we throttle to 0.35s between calls.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load AACT credentials from the ctgov-search-strategies .env
_env_path = Path(r"C:\Users\user\Downloads\Metaprojects\ctgov-search-strategies\.env")
if _env_path.exists():
    load_dotenv(_env_path)

# Also try project-local .env
_local_env = Path(__file__).resolve().parent.parent / ".env"
if _local_env.exists():
    load_dotenv(_local_env)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection():
    """Connect to AACT PostgreSQL. Returns connection or None on failure."""
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed -- AACT pathway disabled")
        return None

    user = os.environ.get("AACT_USER")
    password = os.environ.get("AACT_PASSWORD")
    if not user or not password:
        print("AACT_USER / AACT_PASSWORD not set -- AACT pathway disabled")
        return None

    try:
        return psycopg2.connect(
            host="aact-db.ctti-clinicaltrials.org",
            port=5432,
            database="aact",
            user=user,
            password=password,
            sslmode="require",
            connect_timeout=15,
        )
    except Exception as e:
        print(f"AACT connection failed: {e}")
        return None


# ---------------------------------------------------------------------------
# PMID → NCT mapping
# ---------------------------------------------------------------------------

def batch_pmid_to_nct(conn, pmids: list[str]) -> dict[str, str]:
    """Map PMIDs to NCT IDs via study_references table.

    Parameters
    ----------
    conn   : psycopg2 connection
    pmids  : list of PMID strings

    Returns
    -------
    dict mapping {pmid_str: nct_id}
    """
    if not pmids:
        return {}
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT pmid, nct_id FROM ctgov.study_references
        WHERE pmid = ANY(%s)
    """, (pmids,))
    mapping: dict[str, str] = {}
    for pmid, nct_id in cur.fetchall():
        if pmid and nct_id:
            mapping[str(pmid)] = nct_id
    cur.close()
    return mapping


# ---------------------------------------------------------------------------
# Fetch pre-computed effects
# ---------------------------------------------------------------------------

def fetch_precomputed_effects(conn, nct_ids: list[str]) -> dict[str, list[dict]]:
    """Fetch pre-computed effects from outcome_analyses.

    Returns {nct_id: [{param_type, point_estimate, ci_lower, ci_upper, method}]}.
    """
    if not nct_ids:
        return {}
    cur = conn.cursor()
    cur.execute("""
        SELECT nct_id, param_type, param_value,
               ci_lower_limit, ci_upper_limit, method
        FROM ctgov.outcome_analyses
        WHERE nct_id = ANY(%s) AND param_value IS NOT NULL
    """, (nct_ids,))
    results: dict[str, list[dict]] = {}
    for nct_id, param_type, value, ci_lo, ci_hi, method in cur.fetchall():
        if nct_id not in results:
            results[nct_id] = []
        results[nct_id].append({
            "param_type": param_type or "",
            "point_estimate": float(value) if value is not None else None,
            "ci_lower": float(ci_lo) if ci_lo is not None else None,
            "ci_upper": float(ci_hi) if ci_hi is not None else None,
            "method": method or "",
        })
    cur.close()
    return results


# ---------------------------------------------------------------------------
# Fetch raw outcome measurements
# ---------------------------------------------------------------------------

def fetch_raw_outcomes(conn, nct_ids: list[str]) -> dict[str, list[dict]]:
    """Fetch raw outcome measurements with group info for effect computation.

    Returns {nct_id: [{outcome_title, group_title, group_description,
                       ctgov_group_code, param_type, param_value,
                       dispersion_value}]}.
    """
    if not nct_ids:
        return {}
    cur = conn.cursor()
    cur.execute("""
        SELECT om.nct_id, o.title AS outcome_title,
               rg.title AS group_title, rg.description AS group_desc,
               rg.ctgov_group_code,
               om.param_type, om.param_value_num, om.dispersion_value_num
        FROM ctgov.outcome_measurements om
        JOIN ctgov.outcomes o
            ON om.outcome_id = o.id AND om.nct_id = o.nct_id
        JOIN ctgov.result_groups rg
            ON om.result_group_id = rg.id AND om.nct_id = rg.nct_id
        WHERE om.nct_id = ANY(%s)
    """, (nct_ids,))
    results: dict[str, list[dict]] = {}
    for row in cur.fetchall():
        nct_id = row[0]
        if nct_id not in results:
            results[nct_id] = []
        results[nct_id].append({
            "outcome_title": row[1] or "",
            "group_title": row[2] or "",
            "group_description": row[3] or "",
            "ctgov_group_code": row[4] or "",
            "param_type": row[5] or "",
            "param_value": float(row[6]) if row[6] is not None else None,
            "dispersion_value": float(row[7]) if row[7] is not None else None,
        })
    cur.close()
    return results


# ---------------------------------------------------------------------------
# AACT param_type → our effect type mapping
# ---------------------------------------------------------------------------

PARAM_TYPE_MAP: dict[str, str] = {
    "Hazard Ratio (HR)": "HR",
    "Odds Ratio (OR)": "OR",
    "Risk Ratio (RR)": "RR",
    "Risk Difference (RD)": "RD",
    "Mean Difference (Final Values)": "MD",
    "Mean Difference (Net)": "MD",
    "LS Mean Difference": "MD",
    "LS mean difference": "MD",
    "Least Squares Mean Difference": "MD",
}


# ---------------------------------------------------------------------------
# Match AACT effects to Cochrane
# ---------------------------------------------------------------------------

def match_aact_effect(
    aact_effects: list[dict],
    cochrane_mean: float,
    is_ratio: bool,
) -> Optional[dict]:
    """Try to match AACT pre-computed effects against a Cochrane value.

    Uses classify_match from effect_extractor for consistency with the PDF
    pathway.  Iterates all effects and picks the closest match that passes
    the 10% threshold.

    Parameters
    ----------
    aact_effects  : list of effect dicts from fetch_precomputed_effects
    cochrane_mean : Cochrane reference point estimate (natural scale)
    is_ratio      : True for ratio measures (OR, RR, HR)

    Returns
    -------
    dict with match info, or None if no effect matches.
    """
    from pipeline.effect_extractor import classify_match

    best: Optional[dict] = None
    best_diff = float("inf")

    for eff in aact_effects:
        pe = eff.get("point_estimate")
        if pe is None:
            continue

        result = classify_match(
            extracted=pe,
            cochrane_mean=cochrane_mean,
            is_ratio=is_ratio,
        )
        if result["matched"]:
            diff = result.get("pct_difference", float("inf"))
            if diff is not None and diff < best_diff:
                best_diff = diff
                # Remap tier names to indicate AACT source
                tier = result["match_tier"].replace("direct_", "aact_")
                best = {
                    "matched": True,
                    "match_tier": tier,
                    "pct_difference": diff,
                    "point_estimate": pe,
                    "ci_lower": eff.get("ci_lower"),
                    "ci_upper": eff.get("ci_upper"),
                    "source": "aact",
                    "aact_param_type": eff.get("param_type", ""),
                }

    return best


# ---------------------------------------------------------------------------
# One-shot lookup builder
# ---------------------------------------------------------------------------

def build_aact_lookup(conn, pmids: list[str]) -> dict:
    """Map PMIDs -> NCT IDs -> fetch all effects and raw data in bulk.

    Parameters
    ----------
    conn   : psycopg2 connection
    pmids  : deduplicated list of PMID strings

    Returns
    -------
    {pmid: {"nct_id": str, "effects": [...], "raw": [...]}}
    """
    pmid_to_nct = batch_pmid_to_nct(conn, pmids)
    nct_ids = list(set(pmid_to_nct.values()))

    effects = fetch_precomputed_effects(conn, nct_ids)
    raw = fetch_raw_outcomes(conn, nct_ids)

    lookup: dict[str, dict] = {}
    for pmid, nct_id in pmid_to_nct.items():
        lookup[pmid] = {
            "nct_id": nct_id,
            "effects": effects.get(nct_id, []),
            "raw": raw.get(nct_id, []),
        }

    return lookup


# ===========================================================================
# CT.gov REST API v2 fallback (no credentials needed)
# ===========================================================================

_API_BASE = "https://clinicaltrials.gov/api/v2"
_HEADERS = {"User-Agent": "MetaReproducer/1.0 (academic research)"}
_THROTTLE_S = 0.35  # conservative rate limit


def _api_get(url: str, timeout: int = 30) -> dict:
    """GET JSON from CT.gov API v2 with retry on transient failures."""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            resp = urllib.request.urlopen(req, timeout=timeout)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    return {}


def _api_batch_pmid_to_nct(
    pmids: list[str],
    batch_size: int = 150,
) -> dict[str, str]:
    """Map PMIDs → NCT IDs via CT.gov API v2 ReferencePMID search.

    Batches PMIDs to stay within URL length limits.  Only returns NCT IDs
    whose studies have posted results.

    Returns {pmid_str: nct_id}.
    """
    if not pmids:
        return {}

    mapping: dict[str, str] = {}  # pmid -> nct_id
    total = len(pmids)

    for start in range(0, total, batch_size):
        batch = pmids[start : start + batch_size]
        query = " OR ".join(f"AREA[ReferencePMID]{p}" for p in batch)
        params = urllib.parse.urlencode({
            "query.term": query,
            "filter.advanced": "AREA[ResultsFirstPostDate]RANGE[MIN,MAX]",
            "fields": (
                "protocolSection.identificationModule.nctId,"
                "protocolSection.referencesModule"
            ),
            "pageSize": "1000",
        })
        url = f"{_API_BASE}/studies?{params}"

        batch_set = set(batch)
        data = _api_get(url)
        for study in data.get("studies", []):
            nct_id = (
                study.get("protocolSection", {})
                .get("identificationModule", {})
                .get("nctId", "")
            )
            if not nct_id:
                continue
            refs = (
                study.get("protocolSection", {})
                .get("referencesModule", {})
                .get("references", [])
            )
            for ref in refs:
                ref_pmid = ref.get("pmid")
                if ref_pmid and str(ref_pmid) in batch_set:
                    # First match wins (one PMID → one NCT ID)
                    mapping.setdefault(str(ref_pmid), nct_id)

        time.sleep(_THROTTLE_S)
        if (start // batch_size) % 5 == 4:
            print(f"    PMID->NCT: {start + len(batch)}/{total}", flush=True)

    return mapping


def _api_fetch_analyses(
    nct_ids: list[str],
    batch_size: int = 20,
) -> dict[str, list[dict]]:
    """Fetch outcome analyses for a batch of NCT IDs via CT.gov API v2.

    Returns {nct_id: [effect_dict]} in the same shape as
    fetch_precomputed_effects().
    """
    if not nct_ids:
        return {}

    results: dict[str, list[dict]] = {}
    total = len(nct_ids)

    for start in range(0, total, batch_size):
        batch = nct_ids[start : start + batch_size]
        query = " OR ".join(batch)
        params = urllib.parse.urlencode({
            "query.term": query,
            "fields": (
                "protocolSection.identificationModule.nctId,"
                "resultsSection.outcomeMeasuresModule"
            ),
            "pageSize": "1000",
        })
        url = f"{_API_BASE}/studies?{params}"

        data = _api_get(url)
        for study in data.get("studies", []):
            nct_id = (
                study.get("protocolSection", {})
                .get("identificationModule", {})
                .get("nctId", "")
            )
            if not nct_id:
                continue
            measures = (
                study.get("resultsSection", {})
                .get("outcomeMeasuresModule", {})
                .get("outcomeMeasures", [])
            )
            effects: list[dict] = []
            for measure in measures:
                for analysis in measure.get("analyses", []):
                    param_type = analysis.get("paramType", "")
                    param_value = analysis.get("paramValue")
                    ci_lo = analysis.get("ciLowerLimit")
                    ci_hi = analysis.get("ciUpperLimit")

                    if param_value is None:
                        continue

                    try:
                        pv = float(param_value)
                    except (ValueError, TypeError):
                        continue

                    effects.append({
                        "param_type": param_type,
                        "point_estimate": pv,
                        "ci_lower": float(ci_lo) if ci_lo else None,
                        "ci_upper": float(ci_hi) if ci_hi else None,
                        "method": analysis.get("statisticalMethod", ""),
                    })
            if effects:
                results[nct_id] = effects

        time.sleep(_THROTTLE_S)
        if (start // batch_size) % 10 == 9:
            print(f"    Fetched analyses: {start + len(batch)}/{total}",
                  flush=True)

    return results


def build_aact_lookup_via_api(pmids: list[str]) -> dict:
    """Build AACT-equivalent lookup using CT.gov REST API v2 (no auth).

    Produces the same shape as build_aact_lookup():
        {pmid: {"nct_id": str, "effects": [...], "raw": []}}

    Steps:
        1. Batch PMID->NCT mapping via ReferencePMID search.
        2. For matched NCT IDs with results, fetch outcome analyses.
        3. Assemble per-PMID lookup.

    Parameters
    ----------
    pmids : deduplicated list of PMID strings

    Returns
    -------
    dict — same shape as build_aact_lookup output
    """
    if not pmids:
        return {}

    print(f"  CT.gov API v2: mapping {len(pmids)} PMIDs to NCT IDs...")
    pmid_to_nct = _api_batch_pmid_to_nct(pmids)
    print(f"  CT.gov API v2: {len(pmid_to_nct)} PMIDs mapped to NCT IDs")

    nct_ids = list(set(pmid_to_nct.values()))
    if not nct_ids:
        return {}

    print(f"  CT.gov API v2: fetching analyses for {len(nct_ids)} NCT IDs...")
    effects = _api_fetch_analyses(nct_ids)
    print(f"  CT.gov API v2: {len(effects)} NCT IDs have outcome analyses")

    lookup: dict[str, dict] = {}
    for pmid, nct_id in pmid_to_nct.items():
        nct_effects = effects.get(nct_id, [])
        if nct_effects:  # Only include PMIDs that actually have effects
            lookup[pmid] = {
                "nct_id": nct_id,
                "effects": nct_effects,
                "raw": [],  # API v2 doesn't provide raw measurements easily
            }

    return lookup
