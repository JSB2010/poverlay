#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
API_PORT = int(os.environ.get("POVERLAY_SMOKE_API_PORT", "8787"))
WORKER_PORT = int(os.environ.get("POVERLAY_SMOKE_WORKER_PORT", "47981"))
API_BASE = f"http://127.0.0.1:{API_PORT}"
WORKER_BASE = f"http://127.0.0.1:{WORKER_PORT}"


def _check_python() -> None:
    if not PYTHON.exists():
        raise RuntimeError("Missing .venv Python. Run ./scripts/setup.sh first.")


def _assert_not_running(url: str) -> None:
    try:
        response = requests.get(url, timeout=1)
    except requests.RequestException:
        return
    raise RuntimeError(f"Smoke target is already responding at {url}: HTTP {response.status_code}")


def _wait_json(url: str, *, timeout_seconds: float, name: str) -> dict[str, Any]:
    started = time.monotonic()
    last_error: Exception | None = None
    while time.monotonic() - started < timeout_seconds:
        try:
            response = requests.get(url, timeout=1)
            if response.ok:
                payload = response.json()
                if isinstance(payload, dict):
                    return payload
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {name} at {url}: {last_error}")


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _mock_renderer_source() -> str:
    return """#!/usr/bin/env python3
from pathlib import Path
import sys
import time

output = Path(sys.argv[-1])
output.parent.mkdir(parents=True, exist_ok=True)
for progress in (10, 50, 100):
    print(f"[{progress}%]", flush=True)
    time.sleep(0.05)
output.write_bytes(b"poverlay smoke render\\n")
"""


def _mock_ffmpeg_source() -> str:
    return """#!/usr/bin/env python3
import sys

if "-encoders" in sys.argv:
    print("Encoders:")
    print(" V..... libx264 H.264 / AVC")
elif "-hwaccels" in sys.argv:
    print("Hardware acceleration methods:")
else:
    print("ffmpeg smoke mock")
"""


def _process_log(process: subprocess.Popen[bytes], log_path: Path) -> str:
    if log_path.exists():
        return log_path.read_text(encoding="utf-8", errors="replace")
    return f"{process.args!r} produced no log"


def _start_process(command: list[str], *, env: dict[str, str], log_path: Path) -> subprocess.Popen[bytes]:
    log_handle = log_path.open("wb")
    try:
        return subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
    finally:
        log_handle.close()


def _job_payload() -> dict[str, Any]:
    return {
        "gpx_name": "track.gpx",
        "videos": [
            {
                "input_name": "clip.mp4",
                "title": "Smoke clip",
                "size_bytes": 11,
                "source_resolution": "1920x1080",
                "source_fps": "30",
                "source_duration_seconds": 1.0,
            }
        ],
        "settings": {
            "overlay_theme": "powder-neon",
            "layout_style": "summit-grid",
            "render_profile": "auto",
            "map_style": "osm",
            "speed_units": "mph",
            "gpx_speed_unit": "auto",
            "distance_units": "mile",
            "altitude_units": "feet",
            "temperature_units": "degF",
            "gpx_offset_seconds": 0,
            "fps_mode": "source_exact",
            "fixed_fps": 30,
            "component_visibility": {},
            "include_maps": True,
        },
        "upload_intent": "local_only",
    }


def main() -> int:
    _check_python()
    _assert_not_running(f"{API_BASE}/health")
    _assert_not_running(f"{WORKER_BASE}/health")

    with tempfile.TemporaryDirectory(prefix="poverlay-local-render-smoke-") as raw_tmp:
        tmp = Path(raw_tmp)
        data_dir = tmp / "api-data"
        home_dir = tmp / "home"
        mock_bin_dir = tmp / "bin"
        home_dir.mkdir()
        mock_bin_dir.mkdir()
        renderer = mock_bin_dir / "mock-renderer"
        ffmpeg = mock_bin_dir / "ffmpeg"
        _write_executable(renderer, _mock_renderer_source())
        _write_executable(ffmpeg, _mock_ffmpeg_source())

        api_log = tmp / "api.log"
        worker_log = tmp / "worker.log"
        env = os.environ.copy()
        env.update(
            {
                "API_BASE_URL": API_BASE,
                "WEB_BASE_URL": "http://127.0.0.1:3000",
                "POVERLAY_DATA_DIR": str(data_dir),
                "HOME": str(home_dir),
                "FIREBASE_AUTH_ENABLED": "false",
                "FIRESTORE_ENABLED": "false",
                "R2_UPLOAD_ENABLED": "false",
                "LOCAL_RENDER_ENABLED": "true",
                "POVERLAY_LOCAL_SMOKE_AUTH_UID": "local-smoke-user",
                "POVERLAY_LOCAL_SMOKE_IN_MEMORY_JOBS": "true",
                "POVERLAY_ALLOWED_API_BASES": API_BASE,
                "POVERLAY_ALLOWED_WEB_ORIGINS": "http://127.0.0.1:3000,http://localhost:3000",
                "POVERLAY_LOCAL_RENDERER_BIN": str(renderer),
                "PATH": f"{mock_bin_dir}{os.pathsep}{env.get('PATH', '')}",
                "PYTHONPATH": f"{REPO_ROOT / 'apps' / 'local-worker'}{os.pathsep}{env.get('PYTHONPATH', '')}",
            }
        )

        api_process = _start_process(
            [str(PYTHON), "-m", "uvicorn", "--app-dir", "apps/api", "app.main:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
            env=env,
            log_path=api_log,
        )
        worker_process = _start_process(
            [str(PYTHON), "-m", "poverlay_worker.main", "serve", "--host", "127.0.0.1", "--port", str(WORKER_PORT)],
            env=env,
            log_path=worker_log,
        )

        try:
            _wait_json(f"{API_BASE}/health", timeout_seconds=20, name="API")
            worker_health = _wait_json(f"{WORKER_BASE}/health", timeout_seconds=20, name="local worker")
            if worker_health.get("name") != "POVerlay Local Worker":
                raise RuntimeError(f"Unexpected worker health payload: {worker_health}")

            start = requests.post(f"{API_BASE}/api/local-render/pairing/start", timeout=10)
            start.raise_for_status()
            pairing_code = start.json()["pairing_code"]

            pair = requests.post(
                f"{WORKER_BASE}/pairing/complete",
                json={"api_base_url": API_BASE, "pairing_code": pairing_code},
                timeout=10,
            )
            pair.raise_for_status()
            local_token = pair.json()["local_token"]

            create = requests.post(f"{API_BASE}/api/local-render/jobs", json=_job_payload(), timeout=10)
            create.raise_for_status()
            job = create.json()
            job_id = job["id"]

            files = [
                ("gpx", ("track.gpx", b"<gpx></gpx>\n", "application/gpx+xml")),
                ("videos", ("clip.mp4", b"smoke video", "video/mp4")),
            ]
            submit = requests.post(
                f"{WORKER_BASE}/jobs",
                data={"job_manifest": json.dumps(job)},
                files=files,
                headers={"X-POVerlay-Local-Token": local_token},
                timeout=10,
            )
            submit.raise_for_status()

            deadline = time.monotonic() + 30
            final_job: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                status = requests.get(f"{API_BASE}/api/jobs/{job_id}", timeout=10)
                status.raise_for_status()
                payload = status.json()
                if payload.get("status") in {"completed", "failed", "completed_with_errors"}:
                    final_job = payload
                    break
                time.sleep(0.5)

            if final_job is None:
                raise RuntimeError(f"Timed out waiting for job {job_id} to finish")
            if final_job.get("status") != "completed":
                raise RuntimeError(f"Expected completed job, got {final_job}")
            video = final_job["videos"][0]
            output_path = Path(video["local_output_path"])
            if not output_path.exists():
                raise RuntimeError(f"Local output was not written: {output_path}")

            print(f"Local render HTTP smoke passed: job={job_id} output={output_path}")
            return 0
        except Exception:
            print("API log:", file=sys.stderr)
            print(_process_log(api_process, api_log), file=sys.stderr)
            print("Worker log:", file=sys.stderr)
            print(_process_log(worker_process, worker_log), file=sys.stderr)
            raise
        finally:
            for process in (worker_process, api_process):
                process.terminate()
            deadline = time.monotonic() + 5
            for process in (worker_process, api_process):
                while process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.1)
                if process.poll() is None:
                    process.kill()
            shutil.rmtree(data_dir, ignore_errors=True)
            shutil.rmtree(home_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
