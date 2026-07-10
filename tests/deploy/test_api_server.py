import sys
import json
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.deploy.api_server import JobStore, build_explainer_props


def test_job_store_create_and_get(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_LLM_MODEL", "qwen3-coder:30b")
    store = JobStore(tmp_path)

    job = store.create(
        {
            "prompt": "Make a 60-second animated explainer about agents.",
            "pipeline": "animated-explainer",
            "render_runtime": "remotion",
        }
    )

    assert job["job_id"].startswith("om_")
    assert job["status"] == "queued"
    assert job["model"] == "qwen3-coder:30b"
    assert store.get(job["job_id"])["prompt"] == "Make a 60-second animated explainer about agents."
    assert store.list()[0]["job_id"] == job["job_id"]


def test_build_explainer_props_from_job():
    props = build_explainer_props(
        {
            "prompt": "Make a 30-second animated explainer about local AI.",
            "pipeline": "animated-explainer",
            "render_runtime": "remotion",
        }
    )

    assert props["theme"] == "flat-motion-graphics"
    assert len(props["cuts"]) == 5
    assert props["cuts"][0]["type"] == "hero_title"
    assert props["cuts"][-1]["out_seconds"] == 30


def test_job_store_requires_prompt(tmp_path):
    store = JobStore(tmp_path)

    try:
        store.create({"pipeline": "animated-explainer"})
    except ValueError as exc:
        assert "prompt" in str(exc)
    else:
        raise AssertionError("Expected missing prompt to raise ValueError")


def test_static_librechat_schema_matches_jobs_api():
    schema_path = PROJECT_ROOT / "docs" / "librechat" / "openmontage.openapi.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["openapi"] == "3.1.0"
    assert schema["paths"]["/jobs"]["post"]["operationId"] == "createOpenMontageJob"
    assert "/jobs/{job_id}/outputs" in schema["paths"]
    assert "/jobs/{job_id}/outputs/final.mp4" in schema["paths"]
    assert schema["servers"][0]["url"] == "http://host.docker.internal:3003"


def test_static_librechat_config_allows_openmontage_address():
    config_path = PROJECT_ROOT / "docs" / "librechat" / "librechat.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config["version"] == "1.3.13"
    assert config["endpoints"]["custom"][0]["models"]["default"] == ["qwen3-coder:30b"]
    assert "host.docker.internal:3003" in config["actions"]["allowedAddresses"]
