from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from typing import Any
from uuid import uuid4
import zipfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.gpx_tools import shift_gpx_timestamps
from app.layouts import THEMES, render_layout_xml


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
STATIC_DIR = ROOT / "app" / "static"
CONFIG_DIR = DATA_DIR / "gopro-config"
FFMPEG_PROFILES_FILE = CONFIG_DIR / "ffmpeg-profiles.json"

LOCAL_DASHBOARD_BIN = ROOT / "scripts" / "gopro-dashboard-local.sh"
GOPRO_DASHBOARD_BIN = os.environ.get(
    "GOPRO_DASHBOARD_BIN",
    str(LOCAL_DASHBOARD_BIN if LOCAL_DASHBOARD_BIN.exists() else (ROOT / ".venv" / "bin" / "gopro-dashboard.py")),
)
FFPROBE_BIN = os.environ.get("FFPROBE_BIN", "ffprobe")
DEFAULT_FONT_PATH = os.environ.get("OVERLAY_FONT_PATH", str(STATIC_DIR / "fonts" / "Orbitron-Bold.ttf"))

ALLOWED_UNITS_SPEED = {"kph", "mph", "mps", "knots"}
ALLOWED_UNITS_ALTITUDE = {"metre", "meter", "feet", "foot"}
ALLOWED_UNITS_DISTANCE = {"km", "mile", "nmi", "meter", "metre"}
ALLOWED_UNITS_TEMP = {"degC", "degF", "kelvin"}
ALLOWED_GPX_SPEED_UNITS = {"auto", "mps", "mph", "kph", "knots"}
ALLOWED_MAP_STYLES = {
    "osm",
    "geo-dark-matter",
    "geo-positron",
    "geo-positron-blue",
    "geo-toner",
}
ALLOWED_FPS_MODES = {"source_exact", "source_rounded", "fixed"}
AUTO_RENDER_PROFILE = "auto"

RENDER_PROFILE_CATALOG: dict[str, dict[str, Any]] = {
    "qt-hevc-balanced": {
        "label": "HEVC (QuickTime Balanced) - Recommended",
        "summary": "Best default on macOS for smooth 4K/5.3K playback with strong quality and smaller files.",
        "best_for": "QuickTime, Apple Photos, Final Cut, AirDrop sharing on modern Apple devices.",
        "compatibility": "Excellent on Apple and modern players (VLC, Chrome, Edge).",
        "platforms": {"darwin"},
        "ffmpeg": {
            "input": [],
            "output": [
                "-vcodec",
                "hevc_videotoolbox",
                "-tag:v",
                "hvc1",
                "-b:v",
                "45M",
                "-maxrate",
                "60M",
                "-bufsize",
                "90M",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
            ],
        },
    },
    "qt-hevc-high": {
        "label": "HEVC (QuickTime High Quality)",
        "summary": "Highest quality Apple-targeted export at source resolution with large files.",
        "best_for": "Archival masters and high-detail exports where file size is secondary.",
        "compatibility": "Excellent on Apple and modern HEVC-capable players/devices.",
        "platforms": {"darwin"},
        "ffmpeg": {
            "input": [],
            "output": [
                "-vcodec",
                "hevc_videotoolbox",
                "-tag:v",
                "hvc1",
                "-b:v",
                "70M",
                "-maxrate",
                "90M",
                "-bufsize",
                "140M",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
            ],
        },
    },
    "h264-source": {
        "label": "H.264 (Source Resolution)",
        "summary": "Preserves source resolution with very broad software compatibility.",
        "best_for": "Uploads to editors/services that prefer H.264 while keeping full resolution.",
        "compatibility": "Very broad support, but very high resolutions can still challenge weaker devices.",
        "platforms": {"darwin", "linux", "win32"},
        "ffmpeg": {
            "input": [],
            "output": [
                "-vcodec",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "19",
                "-maxrate",
                "70M",
                "-bufsize",
                "140M",
                "-pix_fmt",
                "yuv420p",
                "-profile:v",
                "high",
                "-movflags",
                "+faststart",
            ],
        },
    },
    "h264-4k-compat": {
        "label": "H.264 (4K Compatibility)",
        "summary": "Downscales >4K clips to 4K for smoother playback on a wider range of devices.",
        "best_for": "Sharing to mixed devices/apps (QuickTime, Windows players, TVs, older phones).",
        "compatibility": "Best cross-device compatibility when your source is 5.3K or other very high resolutions.",
        "platforms": {"darwin", "linux", "win32"},
        "ffmpeg": {
            "input": [],
            "filter": "[0:v][1:v]overlay,scale=min(3840\\,iw):-2:flags=lanczos",
            "output": [
                "-vcodec",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-maxrate",
                "40M",
                "-bufsize",
                "80M",
                "-pix_fmt",
                "yuv420p",
                "-profile:v",
                "high",
                "-level",
                "5.1",
                "-movflags",
                "+faststart",
            ],
        },
    },
    "h264-fast": {
        "label": "H.264 (Fast Draft)",
        "summary": "Fastest exports for previews and iteration; lower compression efficiency.",
        "best_for": "Quick drafts before final renders.",
        "compatibility": "Broad compatibility.",
        "platforms": {"darwin", "linux", "win32"},
        "ffmpeg": {
            "input": [],
            "output": ["-vcodec", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        },
    },
}


RENDER_PROFILE_ORDER = [
    "qt-hevc-balanced",
    "qt-hevc-high",
    "h264-4k-compat",
    "h264-source",
    "h264-fast",
]


def _available_render_profile_ids() -> list[str]:
    platform = sys.platform
    return [
        profile_id
        for profile_id in RENDER_PROFILE_ORDER
        if profile_id in RENDER_PROFILE_CATALOG and platform in RENDER_PROFILE_CATALOG[profile_id]["platforms"]
    ]


AVAILABLE_RENDER_PROFILE_IDS = _available_render_profile_ids()
MANUAL_RENDER_PROFILES = set(AVAILABLE_RENDER_PROFILE_IDS)
ALLOWED_RENDER_PROFILES = {AUTO_RENDER_PROFILE, *MANUAL_RENDER_PROFILES}

if sys.platform == "darwin":
    DEFAULT_RENDER_PROFILE = "qt-hevc-balanced"
else:
    DEFAULT_RENDER_PROFILE = "h264-4k-compat" if "h264-4k-compat" in ALLOWED_RENDER_PROFILES else "h264-source"


JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


app = FastAPI(title="GoPro GPX Overlay Studio")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _safe_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return safe or "file"


def _ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _ffmpeg_profile_presets() -> dict[str, dict[str, Any]]:
    presets: dict[str, dict[str, Any]] = {}
    for profile_id, entry in RENDER_PROFILE_CATALOG.items():
        ffmpeg_profile = {
            "input": list(entry["ffmpeg"].get("input", [])),
            "output": list(entry["ffmpeg"].get("output", [])),
        }
        if "filter" in entry["ffmpeg"]:
            ffmpeg_profile["filter"] = entry["ffmpeg"]["filter"]
        presets[profile_id] = ffmpeg_profile
    return presets


def _ensure_ffmpeg_profiles() -> None:
    _ensure_dirs()
    FFMPEG_PROFILES_FILE.write_text(json.dumps(_ffmpeg_profile_presets(), indent=2), encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_job(job_id: str, **fields: Any) -> None:
    with JOBS_LOCK:
        JOBS[job_id].update(fields)


def _set_video(job_id: str, index: int, **fields: Any) -> None:
    with JOBS_LOCK:
        JOBS[job_id]["videos"][index].update(fields)


def _get_job(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return deepcopy(job)


async def _save_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    await upload.close()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_fps(value: str | None) -> float | None:
    if not value:
        return None
    if "/" in value:
        left, right = value.split("/", 1)
        try:
            denom = float(right)
            if denom == 0:
                return None
            return float(left) / denom
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def _probe_video(path: Path) -> dict[str, Any]:
    cmd = [
        FFPROBE_BIN,
        "-v",
        "error",
        "-show_entries",
        "stream=width,height,codec_type,codec_name,avg_frame_rate:format=duration:format_tags=creation_time",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path.name}: {result.stderr.strip()}")

    payload = json.loads(result.stdout)
    video_stream = next((s for s in payload.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video_stream:
        raise RuntimeError(f"No video stream found in {path.name}")

    duration = payload.get("format", {}).get("duration")
    creation_time = payload.get("format", {}).get("tags", {}).get("creation_time")
    fps_raw = video_stream.get("avg_frame_rate")
    fps = _parse_fps(fps_raw)

    return {
        "width": int(video_stream.get("width", 1920)),
        "height": int(video_stream.get("height", 1080)),
        "duration": float(duration) if duration else None,
        "creation_time": creation_time,
        "codec": video_stream.get("codec_name"),
        "fps": fps,
        "fps_raw": fps_raw,
    }


def _set_file_mtime_from_creation(path: Path, creation_time: str | None) -> None:
    dt = _parse_iso(creation_time)
    if dt is None:
        return
    timestamp = dt.timestamp()
    os.utime(path, (timestamp, timestamp))


def _build_renderer_command(
    gpx_path: Path,
    video_path: Path,
    output_path: Path,
    layout_path: Path,
    settings: dict[str, Any],
    render_profile: str,
) -> list[str]:
    cmd = [
        GOPRO_DASHBOARD_BIN,
        "--font",
        settings["font_path"],
        "--gpx",
        str(gpx_path),
        "--use-gpx-only",
        "--video-time-start",
        "file-modified",
        "--layout",
        "xml",
        "--layout-xml",
        str(layout_path),
        "--map-style",
        settings["map_style"],
        "--units-speed",
        settings["speed_units"],
        "--units-altitude",
        settings["altitude_units"],
        "--units-distance",
        settings["distance_units"],
        "--units-temperature",
        settings["temperature_units"],
        "--config-dir",
        str(CONFIG_DIR),
        "--profile",
        render_profile,
    ]

    fps_mode = settings.get("fps_mode", "source_exact")
    if fps_mode == "source_rounded":
        cmd.append("--overlay-fps-round")
    elif fps_mode == "fixed":
        cmd.extend(["--overlay-fps", str(settings["fixed_fps"])])

    cmd.extend(["--", str(video_path), str(output_path)])
    return cmd


def _render_profile_meta() -> list[dict[str, Any]]:
    available = [
        {
            "id": AUTO_RENDER_PROFILE,
            "label": "Auto (Recommended)",
            "summary": "Automatically selects the best export codec per clip based on resolution and platform.",
            "best_for": "Most users; mixes quality with smooth playback and compatibility.",
            "compatibility": "Uses HEVC on high-res macOS clips and H.264 compatibility presets elsewhere.",
            "is_default": True,
        }
    ]
    for profile_id in AVAILABLE_RENDER_PROFILE_IDS:
        entry = RENDER_PROFILE_CATALOG[profile_id]
        available.append(
            {
                "id": profile_id,
                "label": entry["label"],
                "summary": entry["summary"],
                "best_for": entry["best_for"],
                "compatibility": entry["compatibility"],
                "is_default": False,
            }
        )
    return available


def _theme_meta() -> list[dict[str, str]]:
    return [{"id": key, "label": theme.label} for key, theme in THEMES.items()]


def _auto_render_profile_candidates(metadata: dict[str, Any]) -> list[str]:
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    high_resolution = width > 3840 or height > 2160

    if sys.platform == "darwin":
        if high_resolution:
            return ["qt-hevc-balanced", "h264-4k-compat", "h264-source", "h264-fast"]
        return ["h264-source", "qt-hevc-balanced", "h264-fast"]

    if high_resolution:
        return ["h264-4k-compat", "h264-source", "h264-fast"]
    return ["h264-source", "h264-fast"]


def _select_render_profile(metadata: dict[str, Any], requested_profile: str) -> tuple[str, list[str]]:
    if requested_profile != AUTO_RENDER_PROFILE:
        return requested_profile, [requested_profile]

    candidates = [profile for profile in _auto_render_profile_candidates(metadata) if profile in MANUAL_RENDER_PROFILES]
    if not candidates:
        candidates = [DEFAULT_RENDER_PROFILE]
    return candidates[0], candidates


def _render_profile_label(profile_id: str) -> str:
    if profile_id == AUTO_RENDER_PROFILE:
        return "Auto (Recommended)"
    return RENDER_PROFILE_CATALOG.get(profile_id, {}).get("label", profile_id)


def _run_renderer(
    cmd: list[str],
    log_path: Path,
    job_id: str,
    video_index: int,
    total_videos: int,
) -> tuple[int, str]:
    progress_re = re.compile(r"\[(\s*\d+)%\]")
    last_line = ""

    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"\n=== Renderer attempt at {_utc_now()} ===\n")
        log_file.write(" ".join(cmd) + "\n")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        assert process.stdout is not None
        for line in process.stdout:
            log_file.write(line)
            last_line = line.strip()

            match = progress_re.search(line)
            if match:
                video_progress = int(match.group(1).strip())
                _set_video(job_id, video_index, progress=video_progress)
                overall = int(((video_index + (video_progress / 100.0)) / total_videos) * 100)
                _set_job(job_id, progress=overall, message=f"Rendering {video_index + 1}/{total_videos}")

        return_code = process.wait()

    if last_line:
        _set_video(job_id, video_index, detail=last_line)
    return return_code, last_line


def _process_job(job_id: str) -> None:
    job = _get_job(job_id)
    job_dir = Path(job["job_dir"])
    inputs_dir = job_dir / "inputs"
    outputs_dir = job_dir / "outputs"
    work_dir = job_dir / "work"
    logs_dir = job_dir / "logs"

    outputs_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    _set_job(job_id, status="running", started_at=_utc_now(), progress=1, message="Preparing GPX data")

    source_gpx = inputs_dir / job["gpx_name"]
    shifted_gpx = work_dir / "track-shifted.gpx"
    shift_gpx_timestamps(
        source_gpx,
        shifted_gpx,
        float(job["settings"]["gpx_offset_seconds"]),
        speed_unit=str(job["settings"].get("gpx_speed_unit", "auto")),
    )

    total_videos = len(job["videos"])
    failed_count = 0

    for index, video_state in enumerate(job["videos"]):
        input_name = video_state["input_name"]
        input_path = inputs_dir / input_name

        _set_video(job_id, index, status="running", progress=1, detail="Probing metadata")

        try:
            metadata = _probe_video(input_path)
            _set_file_mtime_from_creation(input_path, metadata.get("creation_time"))
            selected_profile, profile_candidates = _select_render_profile(metadata, job["settings"]["render_profile"])

            layout_xml = render_layout_xml(
                metadata["width"],
                metadata["height"],
                job["settings"]["overlay_theme"],
                include_maps=bool(job["settings"]["include_maps"]),
            )
            layout_path = work_dir / f"layout-{index + 1}.xml"
            layout_path.write_text(layout_xml, encoding="utf-8")

            output_name = f"{Path(input_name).stem}-overlay.mp4"
            output_path = outputs_dir / output_name
            log_path = logs_dir / f"{Path(input_name).stem}.log"

            return_code = 1
            attempted_profile = selected_profile
            last_error: str | None = None

            for profile_idx, profile_id in enumerate(profile_candidates):
                attempted_profile = profile_id
                _set_video(
                    job_id,
                    index,
                    detail=f"Rendering with {profile_id} ({profile_idx + 1}/{len(profile_candidates)})",
                    render_profile=profile_id,
                    render_profile_label=_render_profile_label(profile_id),
                )
                command = _build_renderer_command(
                    gpx_path=shifted_gpx,
                    video_path=input_path,
                    output_path=output_path,
                    layout_path=layout_path,
                    settings=job["settings"],
                    render_profile=profile_id,
                )
                return_code, last_line = _run_renderer(command, log_path, job_id, index, total_videos)
                if return_code == 0:
                    selected_profile = attempted_profile
                    break
                last_error = f"Renderer exited with code {return_code} using profile {profile_id}"
                # Retry other profiles only for likely codec/encode issues.
                if "don't overlap in time" in (last_line or "").lower():
                    break

            if return_code != 0:
                failed_count += 1
                _set_video(
                    job_id,
                    index,
                    status="failed",
                    progress=0,
                    error=last_error or f"Renderer exited with code {return_code}",
                    log_name=log_path.name,
                    source_resolution=f"{metadata['width']}x{metadata['height']}",
                    source_fps=metadata.get("fps_raw"),
                    render_profile_label=_render_profile_label(attempted_profile),
                )
                continue

            _set_video(
                job_id,
                index,
                status="completed",
                progress=100,
                output_name=output_name,
                output_size_bytes=output_path.stat().st_size,
                log_name=log_path.name,
                render_profile=selected_profile,
                render_profile_label=_render_profile_label(selected_profile),
                source_resolution=f"{metadata['width']}x{metadata['height']}",
                source_fps=metadata.get("fps_raw"),
            )
        except Exception as exc:  # noqa: BLE001
            failed_count += 1
            _set_video(job_id, index, status="failed", progress=0, error=str(exc))

    if failed_count == 0:
        _set_job(job_id, status="completed", progress=100, finished_at=_utc_now(), message="All videos rendered")
    elif failed_count < total_videos:
        _set_job(
            job_id,
            status="completed_with_errors",
            progress=100,
            finished_at=_utc_now(),
            message=f"Rendered with {failed_count} failure(s)",
        )
    else:
        _set_job(job_id, status="failed", progress=100, finished_at=_utc_now(), message="Rendering failed")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    return {
        "themes": sorted(THEMES.keys()),
        "theme_options": _theme_meta(),
        "speed_units": sorted(ALLOWED_UNITS_SPEED),
        "gpx_speed_units": sorted(ALLOWED_GPX_SPEED_UNITS),
        "altitude_units": sorted(ALLOWED_UNITS_ALTITUDE),
        "distance_units": sorted(ALLOWED_UNITS_DISTANCE),
        "temperature_units": sorted(ALLOWED_UNITS_TEMP),
        "map_styles": sorted(ALLOWED_MAP_STYLES),
        "fps_modes": sorted(ALLOWED_FPS_MODES),
        "render_profiles": _render_profile_meta(),
        "render_profile_ids": AVAILABLE_RENDER_PROFILE_IDS,
        "default_render_profile": AUTO_RENDER_PROFILE,
    }


@app.post("/api/jobs")
async def create_job(
    gpx: UploadFile = File(...),
    videos: list[UploadFile] = File(...),
    speed_units: str = Form("kph"),
    gpx_speed_unit: str = Form("auto"),
    altitude_units: str = Form("metre"),
    distance_units: str = Form("km"),
    temperature_units: str = Form("degC"),
    map_style: str = Form("osm"),
    gpx_offset_seconds: float = Form(0.0),
    overlay_theme: str = Form("powder-neon"),
    include_maps: bool = Form(True),
    fps_mode: str = Form("source_exact"),
    fixed_fps: float = Form(30.0),
    render_profile: str = Form(AUTO_RENDER_PROFILE),
) -> dict[str, Any]:
    _ensure_ffmpeg_profiles()

    if not gpx.filename or not gpx.filename.lower().endswith(".gpx"):
        raise HTTPException(status_code=400, detail="Please upload a .gpx file")
    if not videos:
        raise HTTPException(status_code=400, detail="Please upload at least one video file")

    if speed_units not in ALLOWED_UNITS_SPEED:
        raise HTTPException(status_code=400, detail=f"Unsupported speed units: {speed_units}")
    if gpx_speed_unit not in ALLOWED_GPX_SPEED_UNITS:
        raise HTTPException(status_code=400, detail=f"Unsupported gpx_speed_unit: {gpx_speed_unit}")
    if altitude_units not in ALLOWED_UNITS_ALTITUDE:
        raise HTTPException(status_code=400, detail=f"Unsupported altitude units: {altitude_units}")
    if distance_units not in ALLOWED_UNITS_DISTANCE:
        raise HTTPException(status_code=400, detail=f"Unsupported distance units: {distance_units}")
    if temperature_units not in ALLOWED_UNITS_TEMP:
        raise HTTPException(status_code=400, detail=f"Unsupported temperature units: {temperature_units}")
    if map_style not in ALLOWED_MAP_STYLES:
        raise HTTPException(status_code=400, detail=f"Unsupported map style: {map_style}")
    if overlay_theme not in THEMES:
        raise HTTPException(status_code=400, detail=f"Unsupported overlay theme: {overlay_theme}")
    if fps_mode not in ALLOWED_FPS_MODES:
        raise HTTPException(status_code=400, detail=f"Unsupported fps mode: {fps_mode}")
    if fps_mode == "fixed" and fixed_fps <= 0:
        raise HTTPException(status_code=400, detail="fixed_fps must be > 0")
    if render_profile not in ALLOWED_RENDER_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unsupported render_profile: {render_profile}")

    if not Path(GOPRO_DASHBOARD_BIN).exists():
        raise HTTPException(
            status_code=500,
            detail=(
                f"Renderer binary not found at {GOPRO_DASHBOARD_BIN}. "
                "Set GOPRO_DASHBOARD_BIN or install gopro-overlay in .venv."
            ),
        )

    font_path = Path(DEFAULT_FONT_PATH)
    if not font_path.exists():
        raise HTTPException(status_code=500, detail=f"Font file not found: {font_path}")

    job_id = uuid4().hex
    job_dir = JOBS_DIR / job_id
    inputs_dir = job_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    gpx_name = _safe_filename(gpx.filename)
    await _save_upload(gpx, inputs_dir / gpx_name)

    video_states: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for index, video in enumerate(videos, start=1):
        original_name = video.filename or f"video-{index}.mp4"
        safe_name = _safe_filename(original_name)
        while safe_name in seen_names:
            safe_name = f"{Path(safe_name).stem}-{index}{Path(safe_name).suffix}"
        seen_names.add(safe_name)

        await _save_upload(video, inputs_dir / safe_name)
        video_states.append(
            {
                "input_name": safe_name,
                "status": "queued",
                "progress": 0,
                "detail": "Queued",
                "error": None,
                "output_name": None,
                "output_size_bytes": None,
                "log_name": None,
                "render_profile": None,
                "render_profile_label": None,
                "source_resolution": None,
                "source_fps": None,
            }
        )

    job_data = {
        "id": job_id,
        "job_dir": str(job_dir),
        "status": "queued",
        "created_at": _utc_now(),
        "started_at": None,
        "finished_at": None,
        "progress": 0,
        "message": "Queued",
        "gpx_name": gpx_name,
        "videos": video_states,
        "settings": {
            "speed_units": speed_units,
            "gpx_speed_unit": gpx_speed_unit,
            "altitude_units": altitude_units,
            "distance_units": distance_units,
            "temperature_units": temperature_units,
            "map_style": map_style,
            "gpx_offset_seconds": gpx_offset_seconds,
            "overlay_theme": overlay_theme,
            "include_maps": include_maps,
            "fps_mode": fps_mode,
            "fixed_fps": fixed_fps,
            "render_profile": render_profile,
            "font_path": str(font_path),
        },
    }

    with JOBS_LOCK:
        JOBS[job_id] = job_data

    threading.Thread(target=_process_job, args=(job_id,), daemon=True).start()

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    outputs_dir = Path(job["job_dir"]) / "outputs"

    for video in job["videos"]:
        if video.get("output_name"):
            name = video["output_name"]
            video["download_url"] = f"/api/jobs/{job_id}/download/{name}"

    job["download_all_url"] = (
        f"/api/jobs/{job_id}/download-all"
        if outputs_dir.exists() and any(v.get("output_name") for v in job["videos"])
        else None
    )

    return job


@app.get("/api/jobs/{job_id}/download/{filename}")
def download_output(job_id: str, filename: str) -> FileResponse:
    job = _get_job(job_id)
    outputs_dir = (Path(job["job_dir"]) / "outputs").resolve()
    target = (outputs_dir / filename).resolve()

    if outputs_dir not in target.parents or not target.exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    return FileResponse(target, filename=target.name, media_type="video/mp4")


@app.get("/api/jobs/{job_id}/log/{filename}")
def download_log(job_id: str, filename: str) -> FileResponse:
    job = _get_job(job_id)
    logs_dir = (Path(job["job_dir"]) / "logs").resolve()
    target = (logs_dir / filename).resolve()

    if logs_dir not in target.parents or not target.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    return FileResponse(target, filename=target.name, media_type="text/plain")


@app.get("/api/jobs/{job_id}/download-all")
def download_all(job_id: str) -> FileResponse:
    job = _get_job(job_id)
    job_dir = Path(job["job_dir"])
    outputs_dir = job_dir / "outputs"
    zip_path = job_dir / "outputs.zip"

    output_files = [v.get("output_name") for v in job["videos"] if v.get("output_name")]
    if not output_files:
        raise HTTPException(status_code=404, detail="No outputs available")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name in output_files:
            source = outputs_dir / file_name
            if source.exists():
                archive.write(source, arcname=source.name)

    return FileResponse(zip_path, filename=f"overlay-renders-{job_id}.zip", media_type="application/zip")
