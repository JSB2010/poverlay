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
from urllib.parse import urlparse

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
WORKER_PORT = int(os.environ.get("POVERLAY_DEPLOYED_SMOKE_WORKER_PORT", "47981"))
WORKER_BASE = f"http://127.0.0.1:{WORKER_PORT}"
TERMINAL_STATES = {"completed", "failed", "completed_with_errors"}


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _optional_env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError(f"Invalid URL for deployed smoke: {url}")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _check_python() -> None:
    if not PYTHON.exists():
        raise RuntimeError("Missing .venv Python. Run ./scripts/setup.sh first.")


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
output.write_bytes(b"poverlay deployed smoke render\\n")
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


def _process_log(process: subprocess.Popen[bytes] | None, log_path: Path) -> str:
    if process is None:
        return "No managed worker process was started."
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


def _wait_worker(timeout_seconds: float = 20) -> dict[str, Any]:
    started = time.monotonic()
    last_error: Exception | None = None
    while time.monotonic() - started < timeout_seconds:
        try:
            response = requests.get(f"{WORKER_BASE}/health", timeout=1)
            if response.ok:
                payload = response.json()
                if isinstance(payload, dict):
                    return payload
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for local worker at {WORKER_BASE}: {last_error}")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _firebase_password_id_token() -> str | None:
    api_key = _optional_env("POVERLAY_DEPLOYED_FIREBASE_API_KEY")
    email = _optional_env("POVERLAY_DEPLOYED_FIREBASE_EMAIL")
    password = _optional_env("POVERLAY_DEPLOYED_FIREBASE_PASSWORD")
    if not any([api_key, email, password]):
        return None
    if not all([api_key, email, password]):
        raise RuntimeError(
            "POVERLAY_DEPLOYED_FIREBASE_API_KEY, POVERLAY_DEPLOYED_FIREBASE_EMAIL, "
            "and POVERLAY_DEPLOYED_FIREBASE_PASSWORD are all required for password sign-in"
        )

    response = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    id_token = payload.get("idToken")
    if not isinstance(id_token, str) or not id_token:
        raise RuntimeError("Firebase password sign-in did not return an idToken")
    return id_token


def _auth_token() -> str:
    static_token = _optional_env("POVERLAY_DEPLOYED_AUTH_TOKEN")
    if static_token:
        return static_token
    fresh_token = _firebase_password_id_token()
    if fresh_token:
        return fresh_token
    raise RuntimeError(
        "Set POVERLAY_DEPLOYED_AUTH_TOKEN, or set POVERLAY_DEPLOYED_FIREBASE_API_KEY, "
        "POVERLAY_DEPLOYED_FIREBASE_EMAIL, and POVERLAY_DEPLOYED_FIREBASE_PASSWORD"
    )


def _job_payload() -> dict[str, Any]:
    return {
        "gpx_name": "track-smoke.gpx",
        "videos": [
            {
                "input_name": "clip-smoke.mp4",
                "title": "POVerlay deployed smoke clip",
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
    api_base = _origin(_required_env("POVERLAY_DEPLOYED_API_BASE"))
    token = _auth_token()
    web_origin = os.environ.get("POVERLAY_DEPLOYED_WEB_ORIGIN", api_base).strip().rstrip("/") or api_base
    start_worker = _bool_env("POVERLAY_DEPLOYED_SMOKE_START_WORKER", True)

    if start_worker:
        _check_python()

    with tempfile.TemporaryDirectory(prefix="poverlay-deployed-local-render-smoke-") as raw_tmp:
        tmp = Path(raw_tmp)
        home_dir = tmp / "home"
        mock_bin_dir = tmp / "bin"
        home_dir.mkdir()
        mock_bin_dir.mkdir()
        renderer = mock_bin_dir / "mock-renderer"
        ffmpeg = mock_bin_dir / "ffmpeg"
        _write_executable(renderer, _mock_renderer_source())
        _write_executable(ffmpeg, _mock_ffmpeg_source())

        worker_log = tmp / "worker.log"
        worker_process: subprocess.Popen[bytes] | None = None
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home_dir),
                "POVERLAY_ALLOWED_API_BASES": api_base,
                "POVERLAY_ALLOWED_WEB_ORIGINS": web_origin,
                "POVERLAY_LOCAL_RENDERER_BIN": str(renderer),
                "PATH": f"{mock_bin_dir}{os.pathsep}{env.get('PATH', '')}",
                "PYTHONPATH": f"{REPO_ROOT / 'apps' / 'local-worker'}{os.pathsep}{env.get('PYTHONPATH', '')}",
            }
        )

        try:
            meta = requests.get(f"{api_base}/api/meta", headers=_auth_headers(token), timeout=10)
            meta.raise_for_status()
            if not bool(meta.json().get("local_render_enabled")):
                raise RuntimeError(f"Local rendering is not enabled on deployed API: {api_base}")

            if start_worker:
                worker_process = _start_process(
                    [str(PYTHON), "-m", "poverlay_worker.main", "serve", "--host", "127.0.0.1", "--port", str(WORKER_PORT)],
                    env=env,
                    log_path=worker_log,
                )
            worker_health = _wait_worker()
            if worker_health.get("name") != "POVerlay Local Worker":
                raise RuntimeError(f"Unexpected worker health payload: {worker_health}")

            start = requests.post(f"{api_base}/api/local-render/pairing/start", headers=_auth_headers(token), timeout=10)
            start.raise_for_status()
            pairing_code = start.json()["pairing_code"]

            pair = requests.post(
                f"{WORKER_BASE}/pairing/complete",
                headers={"Origin": web_origin},
                json={"api_base_url": api_base, "pairing_code": pairing_code},
                timeout=10,
            )
            pair.raise_for_status()
            local_token = pair.json()["local_token"]

            create = requests.post(
                f"{api_base}/api/local-render/jobs",
                headers=_auth_headers(token),
                json=_job_payload(),
                timeout=10,
            )
            create.raise_for_status()
            job = create.json()
            job_id = job["id"]

            files = [
                ("gpx", ("track-smoke.gpx", b"<gpx></gpx>\n", "application/gpx+xml")),
                ("videos", ("clip-smoke.mp4", b"smoke video", "video/mp4")),
            ]
            submit = requests.post(
                f"{WORKER_BASE}/jobs",
                data={"job_manifest": json.dumps(job)},
                files=files,
                headers={"X-POVerlay-Local-Token": local_token},
                timeout=10,
            )
            submit.raise_for_status()

            deadline = time.monotonic() + float(os.environ.get("POVERLAY_DEPLOYED_SMOKE_TIMEOUT_SECONDS", "45"))
            final_job: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                status = requests.get(f"{api_base}/api/jobs/{job_id}", headers=_auth_headers(token), timeout=10)
                status.raise_for_status()
                payload = status.json()
                if payload.get("status") in TERMINAL_STATES:
                    final_job = payload
                    break
                time.sleep(1)

            if final_job is None:
                raise RuntimeError(f"Timed out waiting for deployed job {job_id} to finish")
            if final_job.get("status") != "completed":
                raise RuntimeError(f"Expected completed deployed smoke job, got {final_job}")

            video = final_job["videos"][0]
            output_path = Path(str(video.get("local_output_path") or ""))
            if start_worker and not output_path.exists():
                raise RuntimeError(f"Local output was not written: {output_path}")

            print(f"Deployed local-render smoke passed: api={api_base} job={job_id} output={output_path}")
            return 0
        except Exception:
            print("Worker log:", file=sys.stderr)
            print(_process_log(worker_process, worker_log), file=sys.stderr)
            raise
        finally:
            if worker_process is not None:
                worker_process.terminate()
                deadline = time.monotonic() + 5
                while worker_process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.1)
                if worker_process.poll() is None:
                    worker_process.kill()
            shutil.rmtree(home_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"smoke-deployed-local-render: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
