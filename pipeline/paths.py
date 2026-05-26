from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAIRWISE70_RDA_ENV_VARS = ("METAREPRODUCER_RDA_DIR", "PAIRWISE70_RDA_DIR")
RCT_EXTRACTOR_ENV_VARS = ("METAREPRODUCER_RCT_EXTRACTOR_DIR", "RCT_EXTRACTOR_DIR")
MEGA_DIR_ENV_VARS = ("METAREPRODUCER_MEGA_DIR", "RCT_EXTRACTOR_MEGA_DIR")
CTGOV_ENV_FILE_VARS = ("METAREPRODUCER_CTGOV_ENV", "CTGOV_SEARCH_STRATEGIES_ENV")


def _candidate_drive_roots() -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()
    for anchor in (PROJECT_ROOT.anchor, Path.home().anchor, "C:\\", "D:\\"):
        if not anchor:
            continue
        root = Path(anchor)
        key = str(root).lower()
        if key in seen or not root.exists():
            continue
        seen.add(key)
        roots.append(root)
    return roots


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    return Path(raw).expanduser()


def _glob_paths(pattern: str) -> list[Path]:
    return [Path(match) for match in glob.glob(pattern)]


def _existing_paths(candidates: Iterable[Path | None]) -> list[Path]:
    existing: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None or not candidate.exists():
            continue
        try:
            normalized = candidate.resolve()
        except OSError:
            normalized = candidate
        key = str(normalized).lower()
        if key in seen:
            continue
        seen.add(key)
        existing.append(normalized)
    return existing


def _resolve_first(
    candidates: Iterable[Path | None],
    *,
    label: str,
    env_vars: tuple[str, ...],
    required: bool,
) -> Path | None:
    existing = _existing_paths(candidates)
    if existing:
        return existing[0]
    if required:
        env_hint = " or ".join(env_vars)
        raise FileNotFoundError(
            f"{label} not found. Set {env_hint}, or place the dependency in one of "
            "the standard workspace locations."
        )
    return None


def candidate_pairwise_rda_dirs() -> list[Path]:
    candidates: list[Path | None] = [_env_path(name) for name in PAIRWISE70_RDA_ENV_VARS]
    candidates.extend(
        [
            PROJECT_ROOT / "data" / "rda",
            PROJECT_ROOT / "data-raw" / "Pairwise70" / "data",
        ]
    )
    for root in _candidate_drive_roots():
        candidates.append(root / "Pairwise70" / "data")
        candidates.extend(_glob_paths(str(root / "Projects" / "*" / "Pairwise70" / "data")))
        candidates.extend(
            _glob_paths(
                str(root / "Users" / "*" / "OneDrive - NHS" / "Documents" / "Pairwise70" / "data")
            )
        )
    return _existing_paths(candidates)


def resolve_pairwise_rda_dir(*, required: bool = True) -> Path | None:
    return _resolve_first(
        candidate_pairwise_rda_dirs(),
        label="Pairwise70 RDA directory",
        env_vars=PAIRWISE70_RDA_ENV_VARS,
        required=required,
    )


def candidate_rct_extractor_dirs() -> list[Path]:
    candidates: list[Path | None] = [_env_path(name) for name in RCT_EXTRACTOR_ENV_VARS]
    candidates.extend(
        [
            PROJECT_ROOT.parent / "rct-extractor-v2",
            PROJECT_ROOT / "external" / "rct-extractor-v2",
        ]
    )
    for root in _candidate_drive_roots():
        candidates.append(root / "rct-extractor-v2")
        candidates.extend(_glob_paths(str(root / "Projects" / "*" / "rct-extractor-v2")))
        candidates.extend(_glob_paths(str(root / "Users" / "*" / "rct-extractor-v2")))
    return _existing_paths(candidates)


def resolve_rct_extractor_dir(*, required: bool = True) -> Path | None:
    return _resolve_first(
        candidate_rct_extractor_dirs(),
        label="RCT Extractor checkout",
        env_vars=RCT_EXTRACTOR_ENV_VARS,
        required=required,
    )


def candidate_mega_dirs() -> list[Path]:
    candidates: list[Path | None] = [_env_path(name) for name in MEGA_DIR_ENV_VARS]
    extractor_dir = resolve_rct_extractor_dir(required=False)
    if extractor_dir is not None:
        candidates.append(extractor_dir / "gold_data" / "mega")
    for root in _candidate_drive_roots():
        candidates.append(root / "rct-extractor-v2" / "gold_data" / "mega")
        candidates.extend(_glob_paths(str(root / "Projects" / "*" / "rct-extractor-v2" / "gold_data" / "mega")))
    return _existing_paths(candidates)


def resolve_mega_dir(*, required: bool = True) -> Path | None:
    return _resolve_first(
        candidate_mega_dirs(),
        label="RCT Extractor mega data directory",
        env_vars=MEGA_DIR_ENV_VARS + RCT_EXTRACTOR_ENV_VARS,
        required=required,
    )


def resolve_mega_eval_path(*, required: bool = True) -> Path | None:
    mega_dir = resolve_mega_dir(required=required)
    if mega_dir is None:
        return None
    return _resolve_first(
        [mega_dir / "mega_eval_v10_3_merged.jsonl"],
        label="mega_eval_v10_3_merged.jsonl",
        env_vars=MEGA_DIR_ENV_VARS + RCT_EXTRACTOR_ENV_VARS,
        required=required,
    )


def resolve_mega_matched_path(*, required: bool = True) -> Path | None:
    mega_dir = resolve_mega_dir(required=required)
    if mega_dir is None:
        return None
    return _resolve_first(
        [mega_dir / "mega_matched.jsonl"],
        label="mega_matched.jsonl",
        env_vars=MEGA_DIR_ENV_VARS + RCT_EXTRACTOR_ENV_VARS,
        required=required,
    )


def resolve_mega_pdf_dir(*, required: bool = True) -> Path | None:
    mega_dir = resolve_mega_dir(required=required)
    if mega_dir is None:
        return None
    return _resolve_first(
        [mega_dir / "pdfs"],
        label="mega PDF directory",
        env_vars=MEGA_DIR_ENV_VARS + RCT_EXTRACTOR_ENV_VARS,
        required=required,
    )


def candidate_ctgov_env_files() -> list[Path]:
    candidates: list[Path | None] = [_env_path(name) for name in CTGOV_ENV_FILE_VARS]
    candidates.append(PROJECT_ROOT / ".env")
    for root in _candidate_drive_roots():
        candidates.append(root / "ctgov-search-strategies" / ".env")
        candidates.append(root / "Metaprojects" / "ctgov-search-strategies" / ".env")
        candidates.extend(_glob_paths(str(root / "Projects" / "*" / "ctgov-search-strategies" / ".env")))
        candidates.extend(
            _glob_paths(
                str(root / "Users" / "*" / "Downloads" / "Metaprojects" / "ctgov-search-strategies" / ".env")
            )
        )
    return _existing_paths(candidates)


def load_candidate_dotenvs() -> list[Path]:
    loaded: list[Path] = []
    for env_path in candidate_ctgov_env_files():
        load_dotenv(env_path, override=False)
        loaded.append(env_path)
    return loaded
