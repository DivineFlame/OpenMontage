"""Minimal OpenMontage HTTP API for container deployments.

The API records and exposes jobs without pretending to run the full agentic
production workflow itself.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urlparse


API_VERSION = "0.1.0"
DEFAULT_STATE_DIR = "/workspace/openmontage-api"
DEFAULT_OUTPUT_DIR = "/app/output/openmontage-api"
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_bytes(data: Any, status: int = 200) -> tuple[int, bytes]:
    return status, json.dumps(data, indent=2).encode("utf-8")


class JobStore:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.jobs_dir = state_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("Field 'prompt' is required.")

        job_id = f"om_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        now = utc_now()
        job = {
            "job_id": job_id,
            "status": "queued",
            "stage": "queued",
            "message": (
                "Job accepted by the OpenMontage API. Run an OpenMontage agent "
                "or worker against this job record to produce outputs."
            ),
            "prompt": prompt,
            "pipeline": payload.get("pipeline", "auto"),
            "render_runtime": payload.get("render_runtime", "auto"),
            "model": payload.get("model") or os.environ.get("OPENMONTAGE_LLM_MODEL") or os.environ.get("OLLAMA_MODEL"),
            "metadata": payload.get("metadata") or {},
            "created_at": now,
            "updated_at": now,
            "logs": [
                {
                    "timestamp": now,
                    "level": "info",
                    "message": "OpenMontage job record created.",
                }
            ],
            "outputs": [],
            "command_hint": (
                "Open this repository in your coding agent and ask it to run "
                f"OpenMontage job {job_id} from {self.job_path(job_id)}."
            ),
        }
        self._write(job)
        return job

    def list(self) -> list[dict[str, Any]]:
        jobs = [self._read(path) for path in sorted(self.jobs_dir.glob("*.json"))]
        return sorted(jobs, key=lambda item: item.get("created_at", ""), reverse=True)

    def get(self, job_id: str) -> dict[str, Any] | None:
        if not JOB_ID_RE.match(job_id):
            return None
        path = self.job_path(job_id)
        if not path.exists():
            return None
        return self._read(path)

    def update(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        job = self.get(job_id)
        if job is None:
            return None
        job.update(fields)
        job["updated_at"] = utc_now()
        self._write(job)
        return job

    def append_log(self, job_id: str, level: str, message: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        logs = list(job.get("logs", []))
        logs.append({"timestamp": utc_now(), "level": level, "message": message})
        job["logs"] = logs
        job["updated_at"] = utc_now()
        self._write(job)

    def job_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def _read(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, job: dict[str, Any]) -> None:
        self.job_path(str(job["job_id"])).write_text(
            json.dumps(job, indent=2),
            encoding="utf-8",
        )


def slug_words(text: str, limit: int = 7) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    return " ".join(words[:limit]) or "OpenMontage Video"


def build_explainer_props(job: dict[str, Any]) -> dict[str, Any]:
    prompt = str(job["prompt"]).strip()
    title = slug_words(prompt, 7)
    subtitle = "Generated from a LibreChat/OpenMontage job"
    prompt_sentence = prompt.rstrip(".")

    return {
        "theme": "flat-motion-graphics",
        "cuts": [
            {
                "id": "hook",
                "source": "",
                "type": "hero_title",
                "in_seconds": 0,
                "out_seconds": 4,
                "text": title,
                "subtitle": subtitle,
                "backgroundColor": "#0F172A",
            },
            {
                "id": "brief",
                "source": "",
                "type": "callout",
                "in_seconds": 4,
                "out_seconds": 10,
                "title": "Creative Brief",
                "text": prompt_sentence,
                "callout_type": "info",
                "accentColor": "#22D3EE",
                "backgroundColor": "#0F172A",
                "color": "#F8FAFC",
            },
            {
                "id": "plan",
                "source": "",
                "type": "comparison",
                "in_seconds": 10,
                "out_seconds": 17,
                "title": "From idea to rendered video",
                "leftLabel": "Input",
                "leftValue": "Prompt",
                "rightLabel": "Output",
                "rightValue": "MP4",
                "accentColor": "#A78BFA",
                "backgroundColor": "#0F172A",
                "color": "#F8FAFC",
            },
            {
                "id": "progress",
                "source": "",
                "type": "progress_bar",
                "in_seconds": 17,
                "out_seconds": 23,
                "title": "Production path",
                "progress": 0.78,
                "progressLabel": "Prompt parsed, scenes planned, render queued",
                "progressColor": "#34D399",
                "backgroundColor": "#0F172A",
            },
            {
                "id": "summary",
                "source": "",
                "type": "kpi_grid",
                "in_seconds": 23,
                "out_seconds": 30,
                "title": "OpenMontage job summary",
                "chartData": [
                    {"label": "Pipeline", "value": 1, "change": 0, "suffix": ""},
                    {"label": "Runtime", "value": 1, "change": 0, "suffix": ""},
                    {"label": "Scenes", "value": 5, "change": 0, "suffix": ""},
                ],
                "columns": 3,
                "chartColors": ["#22D3EE", "#A78BFA", "#34D399"],
                "chartAnimation": "cascade",
                "backgroundColor": "#0F172A",
            },
        ],
        "overlays": [
            {
                "type": "section_title",
                "in_seconds": 10.4,
                "out_seconds": 13.3,
                "text": str(job.get("pipeline") or "animated-explainer"),
                "subtitle": str(job.get("render_runtime") or "remotion"),
                "accentColor": "#A78BFA",
            },
            {
                "type": "stat_reveal",
                "in_seconds": 17.5,
                "out_seconds": 21.8,
                "text": "78%",
                "subtitle": "Render plan assembled",
                "accentColor": "#34D399",
                "position": "bottom-right",
            },
        ],
        "captions": [],
        "audio": {},
    }


def find_command(*names: str) -> str | None:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def render_job(job_id: str, store: JobStore) -> None:
    job = store.get(job_id)
    if job is None:
        return

    repo_root = Path(__file__).resolve().parent.parent.parent
    composer_dir = repo_root / "remotion-composer"
    output_root = Path(os.environ.get("OPENMONTAGE_RENDER_OUTPUT_DIR", DEFAULT_OUTPUT_DIR))
    job_output_dir = output_root / job_id
    props_path = job_output_dir / "props.json"
    output_path = job_output_dir / "final.mp4"

    try:
        store.update(job_id, status="running", stage="planning", message="Building Remotion props from job prompt.")
        store.append_log(job_id, "info", "Building prompt-based Remotion explainer props.")
        job_output_dir.mkdir(parents=True, exist_ok=True)
        props_path.write_text(json.dumps(build_explainer_props(job), indent=2), encoding="utf-8")

        npx_cmd = find_command("npx.cmd", "npx", "npx.exe")
        npm_cmd = find_command("npm.cmd", "npm", "npm.exe")
        if not npx_cmd:
            raise RuntimeError("npx was not found in PATH.")
        if not (composer_dir / "node_modules").exists():
            if not npm_cmd:
                raise RuntimeError("npm was not found in PATH and Remotion dependencies are missing.")
            store.update(job_id, stage="setup", message="Installing Remotion dependencies.")
            store.append_log(job_id, "info", "Installing Remotion dependencies.")
            subprocess.run([npm_cmd, "install"], cwd=composer_dir, check=True, capture_output=True, text=True)

        store.update(job_id, stage="render", message="Rendering Remotion video.")
        store.append_log(job_id, "info", f"Rendering {output_path}.")
        subprocess.run(
            [
                npx_cmd,
                "remotion",
                "render",
                "src/index.tsx",
                "Explainer",
                str(output_path),
                "--props",
                str(props_path),
                "--codec",
                "h264",
            ],
            cwd=composer_dir,
            check=True,
            capture_output=True,
            text=True,
        )

        outputs = [
            {
                "type": "video",
                "path": str(output_path),
                "url": f"/jobs/{job_id}/outputs/final.mp4",
            },
            {
                "type": "props",
                "path": str(props_path),
            },
        ]
        store.update(
            job_id,
            status="completed",
            stage="complete",
            message="Video render completed.",
            outputs=outputs,
        )
        store.append_log(job_id, "info", "Video render completed.")
    except Exception as exc:
        store.update(job_id, status="failed", stage="failed", message=str(exc))
        store.append_log(job_id, "error", str(exc))


class OpenMontageApiHandler(BaseHTTPRequestHandler):
    store: JobStore

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in {"/", "/health"}:
            self._send_json(self._health())
            return

        if path == "/jobs":
            self._send_json({"jobs": self.store.list()})
            return

        match = re.fullmatch(r"/jobs/([^/]+)", path)
        if match:
            job = self.store.get(match.group(1))
            self._send_json(job if job else {"error": "Job not found."}, 200 if job else 404)
            return

        match = re.fullmatch(r"/jobs/([^/]+)/logs", path)
        if match:
            job = self.store.get(match.group(1))
            self._send_json({"job_id": match.group(1), "logs": job.get("logs", [])} if job else {"error": "Job not found."}, 200 if job else 404)
            return

        match = re.fullmatch(r"/jobs/([^/]+)/outputs", path)
        if match:
            job = self.store.get(match.group(1))
            self._send_json({"job_id": match.group(1), "outputs": job.get("outputs", [])} if job else {"error": "Job not found."}, 200 if job else 404)
            return

        match = re.fullmatch(r"/jobs/([^/]+)/outputs/final\.mp4", path)
        if match:
            self._send_job_output(match.group(1), "final.mp4")
            return

        self._send_json({"error": "Not found."}, 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path != "/jobs":
            self._send_json({"error": "Not found."}, 404)
            return

        try:
            body = self._read_json_body()
            job = self.store.create(body)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return
        except json.JSONDecodeError:
            self._send_json({"error": "Request body must be valid JSON."}, 400)
            return

        if os.environ.get("OPENMONTAGE_AUTO_RENDER", "true").lower() in {"1", "true", "yes", "on"}:
            Thread(target=render_job, args=(job["job_id"], self.store), daemon=True).start()

        self._send_json(job, 201)

    def _health(self) -> dict[str, Any]:
        return {
            "service": "openmontage",
            "status": "ok",
            "api_version": API_VERSION,
            "time": utc_now(),
            "llm_provider": os.environ.get("OPENMONTAGE_LLM_PROVIDER"),
            "llm_model": os.environ.get("OPENMONTAGE_LLM_MODEL") or os.environ.get("OLLAMA_MODEL"),
            "llm_base_url": os.environ.get("OPENMONTAGE_LLM_BASE_URL") or os.environ.get("OLLAMA_BASE_URL"),
            "jobs_url": "/jobs",
        }

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("Request body is required.")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _send_json(self, data: Any, status: int = 200) -> None:
        code, payload = json_bytes(data, status)
        self.send_response(code)
        self._send_common_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_job_output(self, job_id: str, filename: str) -> None:
        job = self.store.get(job_id)
        if not job:
            self._send_json({"error": "Job not found."}, 404)
            return

        matching_output = None
        for output in job.get("outputs", []):
            if Path(str(output.get("path", ""))).name == filename:
                matching_output = output
                break
        if not matching_output:
            self._send_json({"error": "Output not found."}, 404)
            return

        output_path = Path(str(matching_output["path"]))
        if not output_path.exists():
            self._send_json({"error": "Output file is missing."}, 404)
            return

        payload = output_path.read_bytes()
        self.send_response(200)
        self._send_common_headers()
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    port = int(os.environ.get("OPENMONTAGE_PORT", "3003"))
    state_dir = Path(os.environ.get("OPENMONTAGE_API_STATE_DIR", DEFAULT_STATE_DIR))
    OpenMontageApiHandler.store = JobStore(state_dir)

    server = ThreadingHTTPServer(("0.0.0.0", port), OpenMontageApiHandler)
    print(f"OpenMontage API listening on 0.0.0.0:{port}")
    print(f"OpenMontage API state dir: {state_dir}")
    while True:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"OpenMontage API server recovered from error: {exc}")
            time.sleep(1)


if __name__ == "__main__":
    main()
