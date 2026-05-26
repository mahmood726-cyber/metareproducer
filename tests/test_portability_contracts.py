import json
import os
from pathlib import Path, PurePath


def test_submission_config_path_is_repo_relative():
    config_path = Path(__file__).parent.parent / "e156-submission" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    capsule_path = PurePath(config["path"])

    assert not capsule_path.is_absolute()
    assert config["path"] == ".."


def test_resolve_pairwise_rda_dir_prefers_env_override(monkeypatch, tmp_path):
    from pipeline import paths

    pairwise_dir = tmp_path / "Pairwise70" / "data"
    pairwise_dir.mkdir(parents=True)
    monkeypatch.setenv("METAREPRODUCER_RDA_DIR", str(pairwise_dir))

    resolved = paths.resolve_pairwise_rda_dir(required=True)

    assert resolved == pairwise_dir.resolve()


def test_load_existing_extractions_respects_mega_env_override(monkeypatch, tmp_path):
    from pipeline.effect_extractor import load_existing_extractions

    mega_dir = tmp_path / "mega"
    mega_dir.mkdir(parents=True)
    (mega_dir / "mega_eval_v10_3_merged.jsonl").write_text(
        json.dumps(
            {
                "first_author": "Smith",
                "year": 2005,
                "extracted": [{"effect_type": "RR", "point_estimate": 0.74}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("METAREPRODUCER_MEGA_DIR", str(mega_dir))

    existing = load_existing_extractions()

    assert existing[("Smith", 2005)]["extracted"][0]["point_estimate"] == 0.74


def test_load_candidate_dotenvs_respects_env_override(monkeypatch, tmp_path):
    from pipeline import paths

    env_path = tmp_path / "ctgov.env"
    env_path.write_text("AACT_USER=test-user\nAACT_PASSWORD=test-pass\n", encoding="utf-8")
    monkeypatch.delenv("AACT_USER", raising=False)
    monkeypatch.delenv("AACT_PASSWORD", raising=False)
    monkeypatch.setenv("METAREPRODUCER_CTGOV_ENV", str(env_path))

    loaded = paths.load_candidate_dotenvs()

    assert env_path.resolve() in loaded
    assert os.environ["AACT_USER"] == "test-user"
    assert os.environ["AACT_PASSWORD"] == "test-pass"
