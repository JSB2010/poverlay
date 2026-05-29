from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import sys
import tempfile
import threading
import time
from typing import Any
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from . import __version__
from .api_client import patch_json, post_json
from .profiles import choose_profile, detect_capabilities
from .render import RenderClip, RenderSettings, build_renderer_command, run_renderer_command, write_ffmpeg_profile
from .upload import upload_file_to_presigned_url


DEFAULT_PORT = 47981
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEFAULT_ALLOWED_HOST_SUFFIXES = ("poverlay.com",)
DEFAULT_ALLOWED_METHODS = ("GET", "POST", "OPTIONS")
MP4_EPOCH_OFFSET_SECONDS = 2_082_844_800
MP4_TIMESTAMP_SCAN_BYTES = 16 * 1024 * 1024
DEFAULT_ALLOWED_WEB_ORIGINS = (
    "https://poverlay.com",
    "https://www.poverlay.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
)


@dataclass
class WorkerState:
    api_base_url: str | None = None
    worker_token: str | None = None
    worker_session_id: str | None = None
    local_token: str | None = None
    uid: str | None = None
    current_job_id: str | None = None
    status: str = "idle"


STATE = WorkerState()
STATE_LOCK = threading.Lock()


def _split_env_list(name: str) -> list[str]:
    return [item.strip().rstrip("/") for item in os.getenv(name, "").split(",") if item.strip()]


def _json_response() -> dict[str, Any]:
    with STATE_LOCK:
        return {
            "name": "POVerlay Local Worker",
            "version": __version__,
            "status": STATE.status,
            "paired": bool(STATE.worker_token),
            "worker_session_id": STATE.worker_session_id,
            "current_job_id": STATE.current_job_id,
        }


app = FastAPI(title="POVerlay Local Worker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[*DEFAULT_ALLOWED_WEB_ORIGINS, *_split_env_list("POVERLAY_ALLOWED_WEB_ORIGINS")],
    allow_origin_regex=r"^https://([a-zA-Z0-9-]+\.)?poverlay\.com$",
    allow_methods=[*DEFAULT_ALLOWED_METHODS],
    allow_headers=["*"],
)


def _url_origin(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError("URL must include scheme and hostname")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL scheme must be http or https")
    hostname = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{hostname}{port}"


def _web_origin(value: str) -> str:
    if value == "tauri://localhost":
        return value
    return _url_origin(value)


def _is_local_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "http" and (parsed.hostname or "").lower() in LOCAL_HOSTS


def _host_matches_allowed_suffix(hostname: str, suffixes: tuple[str, ...] = DEFAULT_ALLOWED_HOST_SUFFIXES) -> bool:
    normalized = hostname.lower().strip(".")
    return any(normalized == suffix or normalized.endswith(f".{suffix}") for suffix in suffixes)


def _is_allowed_web_origin(origin: str) -> bool:
    try:
        normalized = _web_origin(origin)
    except ValueError:
        return False

    allowed_origins = set(DEFAULT_ALLOWED_WEB_ORIGINS) | set(_split_env_list("POVERLAY_ALLOWED_WEB_ORIGINS"))
    if normalized in allowed_origins:
        return True
    parsed = urlparse(normalized)
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and _host_matches_allowed_suffix(hostname)


def _validate_api_base_url(api_base_url: str) -> str:
    try:
        origin = _url_origin(api_base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if _is_local_url(origin):
        return origin

    parsed = urlparse(origin)
    hostname = (parsed.hostname or "").lower()
    allowed_bases = set(_split_env_list("POVERLAY_ALLOWED_API_BASES"))
    if origin in allowed_bases:
        return origin
    if parsed.scheme == "https" and _host_matches_allowed_suffix(hostname):
        return origin
    raise HTTPException(status_code=403, detail="This local worker is not allowed to pair with that API host")


def _validate_request_origin(origin: str | None) -> None:
    if not origin:
        return
    if not _is_allowed_web_origin(origin):
        raise HTTPException(status_code=403, detail="This origin is not allowed to pair with POVerlay Desktop")


@app.middleware("http")
async def _private_network_access_middleware(request: Request, call_next):
    origin = request.headers.get("origin")
    requested_private_network = request.headers.get("access-control-request-private-network", "").lower() == "true"
    if request.method == "OPTIONS" and requested_private_network:
        requested_method = request.headers.get("access-control-request-method", "")
        if origin and requested_method in DEFAULT_ALLOWED_METHODS and _is_allowed_web_origin(origin):
            response = PlainTextResponse("OK", status_code=200)
            requested_headers = request.headers.get("access-control-request-headers", "*")
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = ", ".join(DEFAULT_ALLOWED_METHODS)
            response.headers["Access-Control-Allow-Headers"] = requested_headers
            response.headers["Access-Control-Allow-Private-Network"] = "true"
            response.headers["Access-Control-Max-Age"] = "600"
            response.headers["Vary"] = "Origin"
            return response

    response = await call_next(request)
    if requested_private_network and origin and _is_allowed_web_origin(origin):
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


def _require_local_token(token: str | None) -> None:
    with STATE_LOCK:
        expected = STATE.local_token
    if not expected or token != expected:
        raise HTTPException(status_code=401, detail="Invalid local worker token")


def _api_url(path: str) -> str:
    with STATE_LOCK:
        api_base = STATE.api_base_url
    if not api_base:
        raise RuntimeError("Worker is not paired")
    return f"{api_base.rstrip('/')}{path}"


def _worker_token() -> str:
    with STATE_LOCK:
        token = STATE.worker_token
    if not token:
        raise RuntimeError("Worker is not paired")
    return token


def _patch_job(job_id: str, payload: dict[str, Any]) -> None:
    patch_json(_api_url(f"/api/local-render/jobs/{job_id}"), payload, bearer_token=_worker_token())


def _post_worker_api(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return post_json(_api_url(path), payload, bearer_token=_worker_token())


async def _save_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    await upload.close()


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value).strip("._") or "file"


def _job_root(job_id: str) -> Path:
    return Path.home() / "POVerlay" / "Jobs" / _safe_filename(job_id)


def _mp4_timestamp_to_unix_seconds(seconds_since_1904: int) -> float | None:
    unix_seconds = seconds_since_1904 - MP4_EPOCH_OFFSET_SECONDS
    if unix_seconds <= 0:
        return None
    return float(unix_seconds)


def _parse_mp4_creation_time_from_bytes(data: bytes) -> float | None:
    candidates: list[float] = []
    offset = 0
    while True:
        index = data.find(b"mvhd", offset)
        if index < 4:
            break
        box_start = index - 4
        if box_start + 16 > len(data):
            break
        box_size = int.from_bytes(data[box_start : box_start + 4], "big")
        if box_size < 16:
            offset = index + 4
            continue
        version = data[box_start + 8]
        seconds_since_1904: int | None = None
        if version == 0 and box_start + 16 <= len(data):
            seconds_since_1904 = int.from_bytes(data[box_start + 12 : box_start + 16], "big")
        elif version == 1 and box_start + 20 <= len(data):
            high = int.from_bytes(data[box_start + 12 : box_start + 16], "big")
            low = int.from_bytes(data[box_start + 16 : box_start + 20], "big")
            seconds_since_1904 = high * 4_294_967_296 + low
        if seconds_since_1904 is not None:
            unix_seconds = _mp4_timestamp_to_unix_seconds(seconds_since_1904)
            if unix_seconds is not None:
                candidates.append(unix_seconds)
        offset = index + 4
    return min(candidates) if candidates else None


def _read_mp4_creation_time(path: Path) -> float | None:
    if path.suffix.lower() not in {".mp4", ".mov"} or not path.is_file():
        return None
    file_size = path.stat().st_size
    chunks: list[bytes] = []
    with path.open("rb") as handle:
        chunks.append(handle.read(min(file_size, MP4_TIMESTAMP_SCAN_BYTES)))
        if file_size > MP4_TIMESTAMP_SCAN_BYTES:
            handle.seek(max(file_size - MP4_TIMESTAMP_SCAN_BYTES, 0))
            chunks.append(handle.read(MP4_TIMESTAMP_SCAN_BYTES))
    candidates = [value for chunk in chunks if (value := _parse_mp4_creation_time_from_bytes(chunk)) is not None]
    return min(candidates) if candidates else None


def _manifest_video_timestamp(video: dict[str, Any]) -> float | None:
    for key in ("timeline_start_ms", "creation_time_ms", "last_modified_ms"):
        raw_value = video.get(key)
        if raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value / 1000.0
    return None


def _restore_timeline_timestamp(video: dict[str, Any], input_path: Path) -> float | None:
    timestamp = _manifest_video_timestamp(video) or _read_mp4_creation_time(input_path)
    if timestamp is None:
        return None
    now = time.time()
    # Ignore implausible media timestamps instead of making the copied file unusable.
    if timestamp < 946_684_800 or timestamp > now + 366 * 24 * 60 * 60:
        return None
    os.utime(input_path, (timestamp, timestamp))
    return timestamp


def _settings_from_manifest(manifest: dict[str, Any], font_path: Path) -> RenderSettings:
    settings = manifest.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("job_manifest.settings must be an object")
    return RenderSettings(
        font_path=font_path,
        map_style=str(settings.get("map_style", "osm")),
        speed_units=str(settings.get("speed_units", "kph")),
        altitude_units=str(settings.get("altitude_units", "metre")),
        distance_units=str(settings.get("distance_units", "km")),
        temperature_units=str(settings.get("temperature_units", "degC")),
        fps_mode=str(settings.get("fps_mode", "source_exact")),
        fixed_fps=float(settings.get("fixed_fps", 30.0)),
    )


def _default_worker_renderer() -> tuple[Path, list[str]]:
    executable = Path(sys.executable)
    if executable.name.lower().startswith("python"):
        return executable, ["-m", "poverlay_worker.main", "dashboard"]
    return executable, ["dashboard"]


def _bundled_font_path() -> Path | None:
    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(str(bundle_root)) / "fonts" / "Orbitron-Bold.ttf")
    candidates.extend(
        [
            Path(__file__).resolve().parents[3] / "apps" / "api" / "app" / "static" / "fonts" / "Orbitron-Bold.ttf",
            Path.cwd() / "apps" / "api" / "app" / "static" / "fonts" / "Orbitron-Bold.ttf",
        ]
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _font_path_from_manifest(manifest: dict[str, Any]) -> Path:
    raw_font_path = str(manifest.get("font_path") or os.getenv("POVERLAY_LOCAL_FONT_PATH") or "").strip()
    if raw_font_path:
        font_path = Path(raw_font_path).expanduser()
        if font_path.is_file():
            return font_path
    bundled_font = _bundled_font_path()
    if bundled_font is not None:
        return bundled_font
    return Path(raw_font_path or "Roboto-Medium.ttf")


def _run_local_job(job_id: str, manifest: dict[str, Any], gpx_path: Path, video_paths: dict[str, Path]) -> None:
    with STATE_LOCK:
        STATE.status = "rendering"
        STATE.current_job_id = job_id

    try:
        _patch_job(job_id, {"status": "local_running", "progress": 1, "message": "Preparing local render"})
        job_dir = _job_root(job_id)
        work_dir = job_dir / "work"
        outputs_dir = job_dir / "outputs"
        layouts_dir = work_dir / "layouts"
        config_dir = work_dir / "config"
        cache_dir = work_dir / "cache"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        layouts_dir.mkdir(parents=True, exist_ok=True)

        profile = choose_profile(detect_capabilities())
        write_ffmpeg_profile(config_dir, profile)
        renderer_bin_raw = manifest.get("renderer_bin") or os.getenv("POVERLAY_LOCAL_RENDERER_BIN")
        if renderer_bin_raw:
            renderer_bin = Path(str(renderer_bin_raw))
            renderer_args = None
        else:
            renderer_bin, renderer_args = _default_worker_renderer()
        font_path = _font_path_from_manifest(manifest)
        settings = _settings_from_manifest(manifest, font_path)
        videos = manifest.get("videos")
        if not isinstance(videos, list) or not videos:
            raise ValueError("job_manifest.videos must be a non-empty array")

        total = len(videos)
        for index, video in enumerate(videos):
            if not isinstance(video, dict):
                raise ValueError("job_manifest.videos entries must be objects")
            input_name = str(video.get("input_name") or "")
            video_id = str(video.get("id") or "")
            input_path = video_paths.get(input_name)
            if input_path is None:
                raise ValueError(f"Missing uploaded video for {input_name}")
            _restore_timeline_timestamp(video, input_path)

            layout_xml = str(video.get("layout_xml") or "")
            if not layout_xml:
                raise ValueError(f"Missing layout XML for {input_name}")
            layout_path = layouts_dir / f"{Path(input_name).stem}.xml"
            layout_path.write_text(layout_xml, encoding="utf-8")
            output_name = f"{Path(input_name).stem}-overlay.mp4"
            output_path = outputs_dir / output_name
            command = build_renderer_command(
                renderer_bin=renderer_bin,
                renderer_args=renderer_args,
                gpx_path=gpx_path,
                clip=RenderClip(input_path=input_path, output_path=output_path, layout_path=layout_path),
                settings=settings,
                profile=profile,
                config_dir=config_dir,
                cache_dir=cache_dir,
            )

            _patch_job(
                job_id,
                {
                    "status": "local_running",
                    "message": f"Rendering locally {index + 1}/{total}",
                    "videos": [
                        {
                            "video_id": video_id,
                            "status": "local_running",
                            "progress": 1,
                            "render_profile": profile.id,
                            "render_profile_label": profile.label,
                        }
                    ],
                },
            )

            return_code = 1
            for event in run_renderer_command(command):
                if "progress" in event:
                    progress = int(event["progress"])
                    overall = int(((index + progress / 100.0) / total) * 100)
                    _patch_job(
                        job_id,
                        {
                            "status": "local_running",
                            "progress": overall,
                            "message": f"Rendering locally {index + 1}/{total}",
                            "videos": [{"video_id": video_id, "status": "local_running", "progress": progress}],
                        },
                    )
                if "return_code" in event:
                    return_code = int(event["return_code"])

            if return_code != 0:
                raise RuntimeError(f"Renderer exited with code {return_code} for {input_name}")
            output_size = output_path.stat().st_size if output_path.exists() else None
            if str(manifest.get("upload_intent") or "local_only") == "media_library":
                _patch_job(
                    job_id,
                    {
                        "status": "local_uploading",
                        "message": f"Uploading locally rendered output {index + 1}/{total}",
                        "videos": [{"video_id": video_id, "status": "local_uploading", "progress": 100, "output_name": output_name}],
                    },
                )
                upload_target = _post_worker_api(
                    f"/api/local-render/jobs/{job_id}/upload-target",
                    {"video_id": video_id, "output_name": output_name, "content_type": "video/mp4"},
                )
                upload_file_to_presigned_url(output_path, upload_target)
                _post_worker_api(
                    f"/api/local-render/jobs/{job_id}/upload-complete",
                    {
                        "video_id": video_id,
                        "output_name": output_name,
                        "output_size_bytes": output_size,
                        "local_output_path": str(output_path),
                    },
                )
            else:
                _patch_job(
                    job_id,
                    {
                        "videos": [
                            {
                                "video_id": video_id,
                                "status": "completed",
                                "progress": 100,
                                "output_name": output_name,
                                "local_output_path": str(output_path),
                                "output_size_bytes": output_size,
                                "render_profile": profile.id,
                                "render_profile_label": profile.label,
                            }
                        ]
                    },
                )

        _patch_job(job_id, {"status": "completed", "progress": 100, "message": "Local render complete"})
        with STATE_LOCK:
            STATE.status = "idle"
            STATE.current_job_id = None
    except Exception as exc:  # noqa: BLE001
        try:
            _patch_job(job_id, {"status": "failed", "progress": 100, "message": f"Local render failed: {exc}"})
        finally:
            with STATE_LOCK:
                STATE.status = "error"
                STATE.current_job_id = job_id


@app.get("/health")
def health() -> dict[str, Any]:
    return _json_response()


@app.post("/pairing/complete")
def complete_pairing(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    _validate_request_origin(request.headers.get("origin"))
    api_base_url = _validate_api_base_url(str(payload.get("api_base_url") or "").strip())
    pairing_code = str(payload.get("pairing_code") or "").strip()
    if not api_base_url or not pairing_code:
        raise HTTPException(status_code=400, detail="api_base_url and pairing_code are required")

    response = post_json(
        f"{api_base_url}/api/local-render/pairing/complete",
        {
            "pairing_code": pairing_code,
            "worker_version": __version__,
            "worker_platform": f"{platform.system().lower()}-{platform.machine().lower()}",
        },
    )
    local_token = secrets.token_urlsafe(32)
    with STATE_LOCK:
        STATE.api_base_url = api_base_url
        STATE.worker_token = str(response["worker_token"])
        STATE.worker_session_id = str(response["worker_session_id"])
        STATE.uid = str(response["uid"])
        STATE.local_token = local_token
        STATE.status = "idle"
    return {**_json_response(), "local_token": local_token}


@app.post("/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    job_manifest: str = Form(...),
    gpx: UploadFile = File(...),
    videos: list[UploadFile] = File(...),
    x_poverlay_local_token: str | None = Header(default=None, alias="X-POVerlay-Local-Token"),
) -> dict[str, Any]:
    _require_local_token(x_poverlay_local_token)
    manifest = json.loads(job_manifest)
    if not isinstance(manifest, dict):
        raise HTTPException(status_code=400, detail="job_manifest must be an object")
    job_id = str(manifest.get("id") or "")
    if not job_id:
        raise HTTPException(status_code=400, detail="job_manifest.id is required")

    job_dir = _job_root(job_id)
    inputs_dir = job_dir / "inputs"
    if inputs_dir.exists():
        shutil.rmtree(inputs_dir)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    gpx_path = inputs_dir / _safe_filename(gpx.filename or "track.gpx")
    await _save_upload(gpx, gpx_path)

    video_paths: dict[str, Path] = {}
    for video in videos:
        safe_name = _safe_filename(video.filename or "video.mp4")
        destination = inputs_dir / safe_name
        await _save_upload(video, destination)
        video_paths[safe_name] = destination

    background_tasks.add_task(_run_local_job, job_id, manifest, gpx_path, video_paths)
    return {"accepted": True, "job_id": job_id}


def run_service(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    with tempfile.TemporaryDirectory():
        server.run()
