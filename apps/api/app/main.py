from __future__ import annotations

from collections import defaultdict, deque
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import queue
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
from urllib.parse import quote
from uuid import uuid4
import zipfile

from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.config import load_runtime_config
from app.contracts import build_r2_output_object_key
from app.gpx_tools import shift_gpx_timestamps
from app.layouts import (
    COMPONENT_OPTIONS,
    DEFAULT_COMPONENT_VISIBILITY,
    DEFAULT_LAYOUT_STYLE,
    LAYOUT_STYLES,
    THEMES,
    render_layout_xml,
)


def _discover_repo_root() -> Path:
    this_file = Path(__file__).resolve()
    for parent in this_file.parents:
        if (parent / "vendor" / "gopro-dashboard-overlay").exists() and (parent / "scripts").exists():
            return parent
    return this_file.parents[3]


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = _discover_repo_root()
RUNTIME_CONFIG = load_runtime_config(repo_root=REPO_ROOT, service_root=SERVICE_ROOT)
DATA_DIR = RUNTIME_CONFIG.data_dir
JOBS_DIR = DATA_DIR / "jobs"
CONFIG_DIR = DATA_DIR / "gopro-config"
TEMP_DIR = DATA_DIR / "tmp"
ANALYTICS_DIR = DATA_DIR / "analytics"
RENDER_SAMPLES_FILE = ANALYTICS_DIR / "render-samples.jsonl"
FFMPEG_PROFILES_FILE = CONFIG_DIR / "ffmpeg-profiles.json"

GOPRO_DASHBOARD_BIN = RUNTIME_CONFIG.gopro_dashboard_bin
FFPROBE_BIN = RUNTIME_CONFIG.ffprobe_bin
DEFAULT_FONT_PATH = RUNTIME_CONFIG.overlay_font_path

JOB_CLEANUP_ENABLED = RUNTIME_CONFIG.job_cleanup_enabled
JOB_CLEANUP_INTERVAL_SECONDS = RUNTIME_CONFIG.job_cleanup_interval_seconds
JOB_OUTPUT_RETENTION_HOURS = RUNTIME_CONFIG.job_output_retention_hours
DELETE_INPUTS_ON_COMPLETE = RUNTIME_CONFIG.delete_inputs_on_complete
DELETE_WORK_ON_COMPLETE = RUNTIME_CONFIG.delete_work_on_complete
JOB_EXPIRY_MARKER_FILE = ".expires-at"

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
PROFILE_4K_COMPAT_MAX_WIDTH = 3840
X264_PRESETS = {
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
}


def _resolve_x264_preset(env_key: str, default: str) -> str:
    value = str(os.getenv(env_key, default)).strip().lower() or default
    if value in X264_PRESETS:
        return value
    return default


H264_SOURCE_PRESET = _resolve_x264_preset(
    "POVERLAY_H264_SOURCE_PRESET",
    "medium",
)
H264_4K_COMPAT_PRESET = _resolve_x264_preset(
    "POVERLAY_H264_4K_COMPAT_PRESET",
    "medium",
)
H264_FAST_PRESET = _resolve_x264_preset("POVERLAY_H264_FAST_PRESET", "veryfast")

ETA_DEFAULT_MAPS_MULTIPLIER = 1.05
ETA_DEFAULT_SOURCE_ROUNDED_MULTIPLIER = 0.91
ETA_DEFAULT_FIXED_MULTIPLIER_INTERCEPT = 0.32
ETA_DEFAULT_FIXED_MULTIPLIER_SLOPE = 0.02
ETA_DEFAULT_FIXED_MULTIPLIER_MIN = 0.45
ETA_ANCHOR_MEGA_PIXELS = [0.92, 2.07, 4.11, 8.29, 15.87]
ETA_BASE_PROFILE_POINTS: dict[str, list[tuple[float, float]]] = {
    "h264-fast": [(0.92, 0.839), (2.07, 1.182), (4.11, 2.14), (8.29, 3.518), (15.87, 10.776)],
    "h264-source": [(0.92, 0.933), (2.07, 1.231), (4.11, 2.241), (8.29, 3.79), (15.87, 11.402)],
    "h264-4k-compat": [(0.92, 0.867), (2.07, 1.272), (4.11, 2.516), (8.29, 3.698), (15.87, 11.209)],
    "qt-hevc-balanced": [(0.9, 0.75), (2.1, 1.25), (4.1, 2.3), (8.3, 4.4), (15.9, 8.1)],
    "qt-hevc-high": [(0.9, 0.95), (2.1, 1.6), (4.1, 3.0), (8.3, 5.8), (15.9, 10.6)],
}

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
                H264_SOURCE_PRESET,
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
            "filter": "[0:v]scale=min(3840\\,iw):-2:flags=lanczos[main];[main][1:v]overlay",
            "output": [
                "-vcodec",
                "libx264",
                "-preset",
                H264_4K_COMPAT_PRESET,
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
            "output": ["-vcodec", "libx264", "-preset", H264_FAST_PRESET, "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
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
    DEFAULT_RENDER_PROFILE = "h264-source"


TERMINAL_JOB_STATUSES = {"completed", "completed_with_errors", "failed"}
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
# Firestore is the source of truth; this cache only reduces repeated reads within a worker run.
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
FIREBASE_AUTH_ENABLED = RUNTIME_CONFIG.firebase.auth_enabled
FIREBASE_PROJECT_ID = (RUNTIME_CONFIG.firebase.project_id or "").strip()
FIREBASE_CREDENTIALS_JSON = (RUNTIME_CONFIG.firebase.credentials_json or "").strip()
FIREBASE_CREDENTIALS_PATH = (RUNTIME_CONFIG.firebase.credentials_path or "").strip()
FIRESTORE_ENABLED = RUNTIME_CONFIG.firestore.enabled
FIRESTORE_PROJECT_ID = (RUNTIME_CONFIG.firestore.project_id or "").strip()
FIRESTORE_DATABASE_ID = RUNTIME_CONFIG.firestore.database_id
FIRESTORE_USERS_COLLECTION = RUNTIME_CONFIG.firestore.users_collection
FIRESTORE_JOBS_COLLECTION = RUNTIME_CONFIG.firestore.jobs_collection
R2_UPLOAD_ENABLED = RUNTIME_CONFIG.r2.upload_enabled
R2_BUCKET = (RUNTIME_CONFIG.r2.bucket or "").strip()
R2_REGION = RUNTIME_CONFIG.r2.region
R2_ENDPOINT = (RUNTIME_CONFIG.r2.endpoint or "").strip()
R2_ACCESS_KEY_ID = (RUNTIME_CONFIG.r2.access_key_id or "").strip()
R2_SECRET_ACCESS_KEY = (RUNTIME_CONFIG.r2.secret_access_key or "").strip()
R2_SIGNED_URL_TTL_SECONDS = 15 * 60
MEDIA_LIST_MAX_PAGE_SIZE = 100
MEDIA_SORT_FIELDS = {"created_at", "updated_at", "status", "title"}
MEDIA_SORT_ORDERS = {"asc", "desc"}
STATE_RETRY_ATTEMPTS = 3
STATE_RETRY_DELAY_SECONDS = 0.5
UPLOAD_RETRY_ATTEMPTS = 3
UPLOAD_RETRY_DELAY_SECONDS = 1.0
BREVO_NOTIFICATIONS_ENABLED = RUNTIME_CONFIG.brevo.notifications_enabled
BREVO_API_KEY = (RUNTIME_CONFIG.brevo.api_key or "").strip()
BREVO_SENDER_EMAIL = (RUNTIME_CONFIG.brevo.sender_email or "").strip()
BREVO_SENDER_NAME = RUNTIME_CONFIG.brevo.sender_name
BREVO_TEMPLATE_RENDER_COMPLETE_ID = (RUNTIME_CONFIG.brevo.template_render_complete_id or "").strip()
WEB_BASE_URL = RUNTIME_CONFIG.web_base_url.rstrip("/")
_FIREBASE_INIT_LOCK = threading.Lock()
_FIREBASE_AUTH_MODULE: Any | None = None
_FIRESTORE_CLIENT_LOCK = threading.Lock()
_FIRESTORE_CLIENT: Any | None = None
_R2_CLIENT_LOCK = threading.Lock()
_R2_CLIENT: Any | None = None
_BREVO_CLIENT_LOCK = threading.Lock()
_BREVO_CLIENT: Any | None = None
_QUEUE_WORKER_LOCK = threading.Lock()
_QUEUE_WORKER_STARTED = False
JOB_QUEUE: queue.Queue[str] = queue.Queue()
ENQUEUED_JOBS: set[str] = set()
_RENDER_ANALYTICS_LOCK = threading.Lock()
_RENDER_ETA_CACHE_MTIME: float | None = None
_RENDER_ETA_CACHE: dict[str, Any] | None = None
LOGGER = logging.getLogger("poverlay.api")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _ensure_dirs()
    _start_queue_worker()
    _recover_pending_jobs()
    if JOB_CLEANUP_ENABLED:
        threading.Thread(target=_cleanup_loop, name="job-cleanup", daemon=True).start()
    yield


app = FastAPI(title="POVerlay API", lifespan=_lifespan)

ALLOWED_CORS_ORIGINS = list(RUNTIME_CONFIG.cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserSettingsUpdate(BaseModel):
    notifications_enabled: bool


def _safe_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return safe or "file"


def _ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    # FastAPI/Starlette multipart bodies are first spooled to tempfile before our endpoint code runs.
    # Force temp files onto the app data disk so large uploads do not fail on small /tmp mounts.
    tempfile.tempdir = str(TEMP_DIR)
    os.environ["TMPDIR"] = str(TEMP_DIR)
    os.environ["TMP"] = str(TEMP_DIR)
    os.environ["TEMP"] = str(TEMP_DIR)


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


def _utc_after_hours(hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except IsADirectoryError:
        pass


def _safe_rmtree(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


def _retry_operation(
    label: str,
    operation: Any,
    *,
    attempts: int,
    delay_seconds: float,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(delay_seconds * attempt)
    raise RuntimeError(f"{label} failed after {attempts} attempt(s)") from last_error


def _cache_job_state(job: dict[str, Any]) -> None:
    with JOBS_LOCK:
        JOBS[str(job["id"])] = deepcopy(job)


def _firestore_jobs_collection() -> Any:
    if not FIRESTORE_ENABLED:
        raise RuntimeError("Firestore-backed job state is disabled")

    global _FIRESTORE_CLIENT
    if _FIRESTORE_CLIENT is not None:
        return _FIRESTORE_CLIENT.collection(FIRESTORE_JOBS_COLLECTION)

    with _FIRESTORE_CLIENT_LOCK:
        if _FIRESTORE_CLIENT is None:
            try:
                from google.cloud import firestore
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("google-cloud-firestore is unavailable") from exc

            client_kwargs: dict[str, Any] = {}
            if FIRESTORE_PROJECT_ID:
                client_kwargs["project"] = FIRESTORE_PROJECT_ID

            try:
                _FIRESTORE_CLIENT = firestore.Client(database=FIRESTORE_DATABASE_ID, **client_kwargs)
            except TypeError:
                _FIRESTORE_CLIENT = firestore.Client(**client_kwargs)

    return _FIRESTORE_CLIENT.collection(FIRESTORE_JOBS_COLLECTION)


def _firestore_users_collection() -> Any:
    if not FIRESTORE_ENABLED:
        raise RuntimeError("Firestore-backed user state is disabled")
    global _FIRESTORE_CLIENT
    if _FIRESTORE_CLIENT is None:
        _firestore_jobs_collection()
    assert _FIRESTORE_CLIENT is not None
    return _FIRESTORE_CLIENT.collection(FIRESTORE_USERS_COLLECTION)


def _load_or_create_user_profile(uid: str) -> dict[str, Any]:
    if not FIRESTORE_ENABLED:
        return {"uid": uid, "notifications_enabled": True}

    def _read() -> Any:
        return _firestore_users_collection().document(uid).get()

    snapshot = _retry_operation(
        f"Loading user profile {uid}",
        _read,
        attempts=STATE_RETRY_ATTEMPTS,
        delay_seconds=STATE_RETRY_DELAY_SECONDS,
    )

    now = _utc_now()
    if not snapshot.exists:
        profile: dict[str, Any] = {
            "uid": uid,
            "notifications_enabled": True,
            "created_at": now,
            "updated_at": now,
        }

        def _create() -> None:
            _firestore_users_collection().document(uid).set(profile)

        _retry_operation(
            f"Creating user profile {uid}",
            _create,
            attempts=STATE_RETRY_ATTEMPTS,
            delay_seconds=STATE_RETRY_DELAY_SECONDS,
        )
        return profile

    profile = snapshot.to_dict() or {}
    profile.setdefault("uid", uid)
    if "notifications_enabled" not in profile:
        profile["notifications_enabled"] = True
        profile["updated_at"] = now

        def _backfill_pref() -> None:
            _firestore_users_collection().document(uid).set({"notifications_enabled": True, "updated_at": now}, merge=True)

        _retry_operation(
            f"Backfilling notifications preference for {uid}",
            _backfill_pref,
            attempts=STATE_RETRY_ATTEMPTS,
            delay_seconds=STATE_RETRY_DELAY_SECONDS,
        )
    return profile


def _update_user_notification_preference(uid: str, *, notifications_enabled: bool) -> dict[str, Any]:
    profile = _load_or_create_user_profile(uid)
    profile["notifications_enabled"] = bool(notifications_enabled)
    profile["updated_at"] = _utc_now()

    if FIRESTORE_ENABLED:
        def _write() -> None:
            _firestore_users_collection().document(uid).set(
                {
                    "uid": uid,
                    "notifications_enabled": profile["notifications_enabled"],
                    "updated_at": profile["updated_at"],
                },
                merge=True,
            )

        _retry_operation(
            f"Updating notifications preference for {uid}",
            _write,
            attempts=STATE_RETRY_ATTEMPTS,
            delay_seconds=STATE_RETRY_DELAY_SECONDS,
        )

    return profile


def _update_user_profile_contact(uid: str, *, email: str | None, display_name: str | None) -> None:
    if not FIRESTORE_ENABLED:
        return
    payload = {"uid": uid, "updated_at": _utc_now()}
    if email:
        payload["email"] = email
    if display_name:
        payload["display_name"] = display_name
    if len(payload) <= 2:
        return

    def _write() -> None:
        _firestore_users_collection().document(uid).set(payload, merge=True)

    _retry_operation(
        f"Updating user profile contact for {uid}",
        _write,
        attempts=STATE_RETRY_ATTEMPTS,
        delay_seconds=STATE_RETRY_DELAY_SECONDS,
    )


def _lookup_recipient_email(uid: str) -> tuple[str | None, str | None]:
    profile = _load_or_create_user_profile(uid)
    email = str(profile.get("email") or "").strip() or None
    display_name = str(profile.get("display_name") or "").strip() or None
    if email:
        return email, display_name

    if not FIREBASE_AUTH_ENABLED:
        return None, display_name

    try:
        record = _firebase_auth_module().get_user(uid)
        resolved_email = str(record.email or "").strip() or None
        resolved_name = str(record.display_name or "").strip() or display_name
        if resolved_email:
            _update_user_profile_contact(uid, email=resolved_email, display_name=resolved_name)
        return resolved_email, resolved_name
    except HTTPException:
        return None, display_name
    except Exception:  # noqa: BLE001
        LOGGER.exception("Failed looking up recipient email for uid=%s", uid)
        return None, display_name


def _brevo_client() -> Any:
    if not BREVO_NOTIFICATIONS_ENABLED:
        raise RuntimeError("Brevo notifications are disabled")

    global _BREVO_CLIENT
    if _BREVO_CLIENT is not None:
        return _BREVO_CLIENT

    with _BREVO_CLIENT_LOCK:
        if _BREVO_CLIENT is None:
            try:
                import sib_api_v3_sdk
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("sib-api-v3-sdk is unavailable") from exc
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key["api-key"] = BREVO_API_KEY
            _BREVO_CLIENT = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    return _BREVO_CLIENT


def _job_completion_summary(job: dict[str, Any]) -> dict[str, Any]:
    videos = job.get("videos", [])
    total = len(videos)
    completed = sum(1 for item in videos if item.get("status") == "completed")
    failed = sum(1 for item in videos if item.get("status") == "failed")
    status = str(job.get("status") or "")
    status_label = status.replace("_", " ").title()
    media_url = f"{WEB_BASE_URL}/media"
    job_id = str(job.get("id") or "")
    if job_id:
        media_url = f"{media_url}?job={quote(job_id)}"
    return {
        "job_id": job_id,
        "job_status": status,
        "job_status_label": status_label,
        "job_message": str(job.get("message") or ""),
        "total_videos": total,
        "completed_videos": completed,
        "failed_videos": failed,
        "media_url": media_url,
    }


def _send_brevo_completion_email(job: dict[str, Any], *, recipient_email: str, recipient_name: str | None) -> None:
    summary = _job_completion_summary(job)
    status = str(summary["job_status"])
    subject = f"POVerlay render {summary['job_status_label']} (job {summary['job_id']})"
    if status == "completed":
        subject = f"POVerlay render complete (job {summary['job_id']})"
    elif status == "failed":
        subject = f"POVerlay render failed (job {summary['job_id']})"

    greeting = recipient_name or "there"
    html_content = (
        f"<p>Hi {greeting},</p>"
        f"<p>Your POVerlay job <strong>{summary['job_id']}</strong> is <strong>{summary['job_status_label']}</strong>.</p>"
        f"<p>{summary['job_message']}</p>"
        f"<ul>"
        f"<li>Total videos: {summary['total_videos']}</li>"
        f"<li>Completed: {summary['completed_videos']}</li>"
        f"<li>Failed: {summary['failed_videos']}</li>"
        f"</ul>"
        f"<p><a href=\"{summary['media_url']}\">Open your media library</a></p>"
    )
    text_content = (
        f"Hi {greeting},\n\n"
        f"Your POVerlay job {summary['job_id']} is {summary['job_status_label']}.\n"
        f"{summary['job_message']}\n"
        f"Total videos: {summary['total_videos']}\n"
        f"Completed: {summary['completed_videos']}\n"
        f"Failed: {summary['failed_videos']}\n\n"
        f"Open your media library: {summary['media_url']}\n"
    )

    try:
        template_id = int(BREVO_TEMPLATE_RENDER_COMPLETE_ID) if BREVO_TEMPLATE_RENDER_COMPLETE_ID else None
    except ValueError as exc:
        raise RuntimeError("BREVO_TEMPLATE_RENDER_COMPLETE_ID must be numeric") from exc

    try:
        import sib_api_v3_sdk
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("sib-api-v3-sdk is unavailable") from exc

    payload: dict[str, Any] = {
        "sender": {"email": BREVO_SENDER_EMAIL, "name": BREVO_SENDER_NAME},
        "to": [{"email": recipient_email}],
        "headers": {"X-POVerlay-Job-ID": summary["job_id"]},
    }

    if template_id is not None:
        payload["template_id"] = template_id
        payload["params"] = summary
    else:
        payload["subject"] = subject
        payload["html_content"] = html_content
        payload["text_content"] = text_content

    message = sib_api_v3_sdk.SendSmtpEmail(**payload)
    _brevo_client().send_transac_email(message)


def _send_job_completion_notification(job: dict[str, Any]) -> None:
    if not BREVO_NOTIFICATIONS_ENABLED:
        return

    uid = str(job.get("uid") or "")
    if not uid:
        LOGGER.warning("Skipping completion notification: missing job uid for job=%s", job.get("id"))
        return

    profile = _load_or_create_user_profile(uid)
    if not bool(profile.get("notifications_enabled", True)):
        return

    recipient_email, recipient_name = _lookup_recipient_email(uid)
    if not recipient_email:
        LOGGER.warning("Skipping completion notification: no recipient email for uid=%s job=%s", uid, job.get("id"))
        return

    _send_brevo_completion_email(job, recipient_email=recipient_email, recipient_name=recipient_name)


def _persist_job_state(job: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(job)
    payload["updated_at"] = _utc_now()
    job_id = str(payload["id"])

    def _write() -> None:
        _firestore_jobs_collection().document(job_id).set(payload)

    _retry_operation(
        f"Persisting job {job_id} state",
        _write,
        attempts=STATE_RETRY_ATTEMPTS,
        delay_seconds=STATE_RETRY_DELAY_SECONDS,
    )
    _cache_job_state(payload)
    return payload


def _load_job_state(job_id: str, *, prefer_cache: bool) -> dict[str, Any] | None:
    if prefer_cache:
        with JOBS_LOCK:
            cached = JOBS.get(job_id)
            if cached is not None:
                return deepcopy(cached)

    if not FIRESTORE_ENABLED:
        return None

    def _read() -> Any:
        return _firestore_jobs_collection().document(job_id).get()

    snapshot = _retry_operation(
        f"Loading job {job_id} state",
        _read,
        attempts=STATE_RETRY_ATTEMPTS,
        delay_seconds=STATE_RETRY_DELAY_SECONDS,
    )
    if not snapshot.exists:
        return None

    job_payload = snapshot.to_dict() or {}
    job_payload.setdefault("id", job_id)
    _cache_job_state(job_payload)
    return deepcopy(job_payload)


def _list_jobs_with_status(statuses: set[str]) -> list[dict[str, Any]]:
    if not FIRESTORE_ENABLED:
        return []

    def _stream() -> list[Any]:
        return list(_firestore_jobs_collection().stream())

    snapshots = _retry_operation(
        "Listing job states",
        _stream,
        attempts=STATE_RETRY_ATTEMPTS,
        delay_seconds=STATE_RETRY_DELAY_SECONDS,
    )
    jobs: list[dict[str, Any]] = []
    for snapshot in snapshots:
        payload = snapshot.to_dict() or {}
        payload.setdefault("id", snapshot.id)
        if payload.get("status") in statuses:
            jobs.append(payload)
    return jobs


def _list_jobs_for_uid(uid: str) -> list[dict[str, Any]]:
    if not FIRESTORE_ENABLED:
        return []

    def _stream() -> list[Any]:
        return list(_firestore_jobs_collection().stream())

    snapshots = _retry_operation(
        f"Listing jobs for user {uid}",
        _stream,
        attempts=STATE_RETRY_ATTEMPTS,
        delay_seconds=STATE_RETRY_DELAY_SECONDS,
    )
    jobs: list[dict[str, Any]] = []
    for snapshot in snapshots:
        payload = snapshot.to_dict() or {}
        payload.setdefault("id", snapshot.id)
        if str(payload.get("uid") or "") == uid:
            jobs.append(payload)
    return jobs


def _default_video_title(video: dict[str, Any]) -> str:
    candidate = str(video.get("title") or "").strip()
    if candidate:
        return candidate

    output_name = str(video.get("output_name") or "").strip()
    input_name = str(video.get("input_name") or "").strip()
    base_name = output_name or input_name or "render"
    stem = Path(base_name).stem
    return stem or base_name


def _ensure_video_identity_metadata(job: dict[str, Any]) -> dict[str, Any]:
    changed = False
    videos = job.get("videos", [])
    if not isinstance(videos, list):
        return job

    for video in videos:
        if not isinstance(video, dict):
            continue

        video_id = str(video.get("id") or "").strip()
        if not video_id:
            video["id"] = uuid4().hex
            changed = True

        title = str(video.get("title") or "").strip()
        if not title:
            video["title"] = _default_video_title(video)
            changed = True

    if changed:
        return _persist_job_state(job)
    return job


def _find_video_by_id(job: dict[str, Any], video_id: str) -> tuple[int, dict[str, Any]]:
    videos = job.get("videos", [])
    if not isinstance(videos, list):
        raise HTTPException(status_code=404, detail="Media not found")

    for index, video in enumerate(videos):
        if not isinstance(video, dict):
            continue
        if str(video.get("id") or "") == video_id:
            return index, video

    raise HTTPException(status_code=404, detail="Media not found")


def _media_status_rank(status: str) -> int:
    rank = {
        "queued": 0,
        "running": 1,
        "completed": 2,
        "completed_with_errors": 3,
        "failed": 4,
    }
    return rank.get(status, 99)


def _media_sort_value(item: dict[str, Any], sort_by: str) -> tuple[Any, Any]:
    if sort_by == "status":
        return (_media_status_rank(str(item.get("status") or "")), str(item.get("title") or "").lower())
    if sort_by == "title":
        return (str(item.get("title") or "").lower(), str(item.get("updated_at") or ""))
    return (str(item.get(sort_by) or ""), str(item.get("title") or "").lower())


def _build_media_item(job: dict[str, Any], video: dict[str, Any]) -> dict[str, Any]:
    status = str(video.get("status") or "queued")
    output_name = str(video.get("output_name") or "")
    object_key = str(video.get("r2_object_key") or "")

    return {
        "id": str(video.get("id") or ""),
        "job_id": str(job.get("id") or ""),
        "status": status,
        "job_status": str(job.get("status") or ""),
        "job_message": str(job.get("message") or ""),
        "title": _default_video_title(video),
        "input_name": str(video.get("input_name") or ""),
        "output_name": output_name or None,
        "size_bytes": video.get("output_size_bytes"),
        "render_profile_label": video.get("render_profile_label"),
        "source_resolution": video.get("source_resolution"),
        "source_fps": video.get("source_fps"),
        "source_duration_seconds": video.get("source_duration_seconds"),
        "output_resolution": video.get("output_resolution"),
        "output_fps": video.get("output_fps"),
        "output_duration_seconds": video.get("output_duration_seconds"),
        "output_codec": video.get("output_codec"),
        "render_elapsed_seconds": video.get("render_elapsed_seconds"),
        "wall_x_realtime": video.get("wall_x_realtime"),
        "progress": int(video.get("progress") or 0),
        "detail": video.get("detail"),
        "error": video.get("error"),
        "log_name": str(video.get("log_name") or "") or None,
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "can_download": bool(output_name and object_key and status == "completed"),
    }


def _delete_r2_object(object_key: str) -> None:
    def _delete() -> None:
        _r2_client().delete_object(Bucket=R2_BUCKET, Key=object_key)

    _retry_operation(
        f"Deleting R2 object {object_key}",
        _delete,
        attempts=UPLOAD_RETRY_ATTEMPTS,
        delay_seconds=UPLOAD_RETRY_DELAY_SECONDS,
    )


def _r2_client() -> Any:
    if not R2_UPLOAD_ENABLED:
        raise RuntimeError("R2 upload integration is disabled")

    global _R2_CLIENT
    if _R2_CLIENT is not None:
        return _R2_CLIENT

    with _R2_CLIENT_LOCK:
        if _R2_CLIENT is None:
            try:
                import boto3
                from botocore.config import Config as BotoConfig
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("boto3/botocore is unavailable") from exc

            _R2_CLIENT = boto3.client(
                "s3",
                aws_access_key_id=R2_ACCESS_KEY_ID,
                aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                region_name=R2_REGION,
                endpoint_url=R2_ENDPOINT,
                config=BotoConfig(signature_version="s3v4"),
            )

    return _R2_CLIENT


def _upload_output_to_r2(uid: str, job_id: str, output_name: str, output_path: Path) -> dict[str, Any]:
    object_key = build_r2_output_object_key(uid, job_id, output_name)
    content_type = "video/mp4" if output_path.suffix.lower() == ".mp4" else "application/octet-stream"

    def _upload() -> None:
        _r2_client().upload_file(
            str(output_path),
            R2_BUCKET,
            object_key,
            ExtraArgs={"ContentType": content_type},
        )

    _retry_operation(
        f"Uploading {output_name} to R2",
        _upload,
        attempts=UPLOAD_RETRY_ATTEMPTS,
        delay_seconds=UPLOAD_RETRY_DELAY_SECONDS,
    )

    def _head() -> dict[str, Any]:
        return _r2_client().head_object(Bucket=R2_BUCKET, Key=object_key)

    metadata = _retry_operation(
        f"Verifying R2 upload for {output_name}",
        _head,
        attempts=UPLOAD_RETRY_ATTEMPTS,
        delay_seconds=UPLOAD_RETRY_DELAY_SECONDS,
    )

    etag = metadata.get("ETag")
    return {
        "r2_object_key": object_key,
        "r2_bucket": R2_BUCKET,
        "r2_etag": etag.strip('"') if isinstance(etag, str) else None,
        "r2_uploaded_at": _utc_now(),
        "output_size_bytes": int(metadata.get("ContentLength") or output_path.stat().st_size),
    }


def _signed_r2_download_url(object_key: str, filename: str) -> str:
    safe_filename = quote(_safe_filename(filename))
    content_disposition = f"attachment; filename*=UTF-8''{safe_filename}"

    def _sign() -> str:
        return _r2_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": R2_BUCKET,
                "Key": object_key,
                "ResponseContentDisposition": content_disposition,
            },
            ExpiresIn=R2_SIGNED_URL_TTL_SECONDS,
        )

    return _retry_operation(
        f"Signing download URL for {object_key}",
        _sign,
        attempts=UPLOAD_RETRY_ATTEMPTS,
        delay_seconds=UPLOAD_RETRY_DELAY_SECONDS,
    )


def _enqueue_job(job_id: str) -> None:
    with _QUEUE_WORKER_LOCK:
        if job_id in ENQUEUED_JOBS:
            return
        ENQUEUED_JOBS.add(job_id)
    JOB_QUEUE.put(job_id)


def _queue_worker_loop() -> None:
    while True:
        job_id = JOB_QUEUE.get()
        try:
            _process_job(job_id)
        except Exception as exc:  # noqa: BLE001
            try:
                _set_job(
                    job_id,
                    status="failed",
                    progress=100,
                    finished_at=_utc_now(),
                    message=f"Worker crashed: {exc}",
                )
            except Exception:  # noqa: BLE001
                pass
        finally:
            with _QUEUE_WORKER_LOCK:
                ENQUEUED_JOBS.discard(job_id)
            JOB_QUEUE.task_done()


def _start_queue_worker() -> None:
    global _QUEUE_WORKER_STARTED
    with _QUEUE_WORKER_LOCK:
        if _QUEUE_WORKER_STARTED:
            return
        threading.Thread(target=_queue_worker_loop, name="render-job-worker", daemon=True).start()
        _QUEUE_WORKER_STARTED = True


def _recover_pending_jobs() -> None:
    for job in _list_jobs_with_status({"queued", "running"}):
        job_id = str(job.get("id") or "")
        if not job_id:
            continue

        job_dir_raw = str(job.get("job_dir") or "")
        if not job_dir_raw or not Path(job_dir_raw).exists():
            job["status"] = "failed"
            job["finished_at"] = _utc_now()
            job["progress"] = 100
            job["message"] = "Job artifacts are missing on disk after restart"
            _persist_job_state(job)
            continue

        if job.get("status") == "running":
            job["status"] = "queued"
            job["message"] = "Resuming after API restart"
            for video in job.get("videos", []):
                if video.get("status") == "running":
                    video["status"] = "queued"
                    video["detail"] = "Queued after API restart"
            _persist_job_state(job)

        _enqueue_job(job_id)


def _require_durable_pipeline_enabled() -> None:
    if not FIRESTORE_ENABLED:
        raise HTTPException(status_code=503, detail="Firestore job persistence is disabled")
    if not R2_UPLOAD_ENABLED:
        raise HTTPException(status_code=503, detail="R2 output upload is disabled")


def _is_active_job(job_id: str) -> bool:
    current = _load_job_state(job_id, prefer_cache=False)
    if current is None:
        return False
    return current.get("status") not in TERMINAL_JOB_STATUSES


def _forget_job(job_id: str) -> None:
    with JOBS_LOCK:
        JOBS.pop(job_id, None)


def _write_expiry_marker(job_dir: Path, expires_at: str) -> None:
    (job_dir / JOB_EXPIRY_MARKER_FILE).write_text(expires_at, encoding="utf-8")


def _read_expiry_marker(job_dir: Path) -> datetime | None:
    marker = job_dir / JOB_EXPIRY_MARKER_FILE
    if not marker.exists():
        return None
    return _parse_iso(marker.read_text(encoding="utf-8").strip())


def _cleanup_completed_job_live_files(job_dir: Path) -> None:
    # Inputs/work are not needed after rendering completes.
    if DELETE_INPUTS_ON_COMPLETE:
        _safe_rmtree(job_dir / "inputs")
    if DELETE_WORK_ON_COMPLETE:
        _safe_rmtree(job_dir / "work")
    _safe_rmtree(job_dir / "outputs")
    _safe_rmtree(job_dir / "logs")
    # Remove legacy persistent zip bundles if they exist.
    _safe_unlink(job_dir / "outputs.zip")


def _cleanup_expired_jobs_once() -> None:
    if not JOBS_DIR.exists():
        return

    now = datetime.now(timezone.utc)
    for job_dir in JOBS_DIR.iterdir():
        if not job_dir.is_dir():
            continue

        job_id = job_dir.name
        if _is_active_job(job_id):
            continue

        expires_at = _read_expiry_marker(job_dir)
        if expires_at is None:
            # Backfill retention for old jobs without marker metadata.
            mtime = datetime.fromtimestamp(job_dir.stat().st_mtime, tz=timezone.utc)
            expires_at = mtime + timedelta(hours=JOB_OUTPUT_RETENTION_HOURS)

        if expires_at > now:
            continue

        _safe_rmtree(job_dir)
        _forget_job(job_id)


def _cleanup_loop() -> None:
    while True:
        try:
            _cleanup_expired_jobs_once()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(JOB_CLEANUP_INTERVAL_SECONDS)


def _set_job(job_id: str, **fields: Any) -> None:
    current = _load_job_state(job_id, prefer_cache=True)
    if current is None:
        raise RuntimeError(f"Job {job_id} not found")
    previous_status = str(current.get("status") or "")
    current.update(fields)
    persisted = _persist_job_state(current)

    new_status = str(persisted.get("status") or "")
    if previous_status != new_status and new_status in TERMINAL_JOB_STATUSES:
        try:
            _send_job_completion_notification(persisted)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Job completion notification failed for job=%s status=%s", job_id, new_status)


def _set_video(job_id: str, index: int, **fields: Any) -> None:
    current = _load_job_state(job_id, prefer_cache=True)
    if current is None:
        raise RuntimeError(f"Job {job_id} not found")
    current["videos"][index].update(fields)
    _persist_job_state(current)


def _bearer_token_from_header(authorization: str | None = Header(default=None, alias="Authorization")) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    return token.strip()


def _firebase_auth_module() -> Any:
    global _FIREBASE_AUTH_MODULE
    if _FIREBASE_AUTH_MODULE is not None:
        return _FIREBASE_AUTH_MODULE

    if not FIREBASE_AUTH_ENABLED:
        raise HTTPException(status_code=503, detail="Firebase auth is disabled")

    with _FIREBASE_INIT_LOCK:
        if _FIREBASE_AUTH_MODULE is not None:
            return _FIREBASE_AUTH_MODULE

        try:
            import firebase_admin
            from firebase_admin import auth as firebase_auth
            from firebase_admin import credentials
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail="Firebase auth is unavailable") from exc

        options = {"projectId": FIREBASE_PROJECT_ID} if FIREBASE_PROJECT_ID else None
        if not firebase_admin._apps:
            if FIREBASE_CREDENTIALS_JSON:
                try:
                    credential_payload = json.loads(FIREBASE_CREDENTIALS_JSON)
                except json.JSONDecodeError as exc:
                    raise HTTPException(status_code=500, detail="Invalid FIREBASE_CREDENTIALS_JSON") from exc
                firebase_admin.initialize_app(credentials.Certificate(credential_payload), options=options)
            elif FIREBASE_CREDENTIALS_PATH:
                firebase_admin.initialize_app(credentials.Certificate(FIREBASE_CREDENTIALS_PATH), options=options)
            else:
                firebase_admin.initialize_app(options=options)

        _FIREBASE_AUTH_MODULE = firebase_auth
        return _FIREBASE_AUTH_MODULE


def _verify_firebase_token(token: str) -> str:
    try:
        decoded = _firebase_auth_module().verify_id_token(token, check_revoked=True)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    uid = decoded.get("uid") or decoded.get("sub")
    if not isinstance(uid, str) or not uid:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return uid


def _require_user_uid(token: str = Depends(_bearer_token_from_header)) -> str:
    return _verify_firebase_token(token)


def _get_job(job_id: str, requester_uid: str | None = None) -> dict[str, Any]:
    job = _load_job_state(job_id, prefer_cache=False)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if requester_uid is not None and job.get("uid") != requester_uid:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _find_video_for_filename(job: dict[str, Any], filename: str) -> dict[str, Any] | None:
    for video in job.get("videos", []):
        if video.get("output_name") == filename:
            return video
    return None


def _job_has_only_uploaded_outputs(job: dict[str, Any]) -> bool:
    for video in job.get("videos", []):
        if video.get("output_name") and not video.get("r2_object_key"):
            return False
    return True


def _cleanup_local_artifacts_if_uploaded(job_id: str) -> None:
    job = _get_job(job_id)
    # Keep failed-job artifacts/logs available for troubleshooting.
    if job.get("status") not in {"completed", "completed_with_errors"}:
        return
    if not _job_has_only_uploaded_outputs(job):
        return

    job_dir = Path(str(job.get("job_dir") or ""))
    if job_dir.exists():
        _cleanup_completed_job_live_files(job_dir)
        _safe_rmtree(job_dir)

    _set_job(job_id, local_artifacts_deleted_at=_utc_now())


def _build_zip_from_r2(outputs: list[tuple[str, str]], zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for output_name, object_key in outputs:
            def _download() -> bytes:
                payload = _r2_client().get_object(Bucket=R2_BUCKET, Key=object_key)
                body = payload.get("Body")
                if body is None:
                    raise RuntimeError(f"Missing R2 body for {object_key}")
                return body.read()

            file_bytes = _retry_operation(
                f"Downloading {object_key} from R2",
                _download,
                attempts=UPLOAD_RETRY_ATTEMPTS,
                delay_seconds=UPLOAD_RETRY_DELAY_SECONDS,
            )
            archive.writestr(output_name, file_bytes)


async def _save_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    await upload.close()


async def _probe_video_safe(path: Path) -> dict[str, Any] | None:
    try:
        return await run_in_threadpool(_probe_video, path)
    except Exception:  # noqa: BLE001
        return None


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


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not (parsed > 0):
        return None
    return parsed


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _nearest_eta_anchor(mega_pixels: float) -> float:
    if mega_pixels <= 0:
        return ETA_ANCHOR_MEGA_PIXELS[0]
    return min(ETA_ANCHOR_MEGA_PIXELS, key=lambda anchor: abs(anchor - mega_pixels))


def _interpolate_eta_points(points: list[tuple[float, float]], mega_pixels: float) -> float:
    if not points:
        return 1.0
    if mega_pixels <= points[0][0]:
        return points[0][1]
    for index in range(1, len(points)):
        previous = points[index - 1]
        current = points[index]
        if mega_pixels <= current[0]:
            span = current[0] - previous[0]
            if span <= 0:
                return current[1]
            ratio = (mega_pixels - previous[0]) / span
            return previous[1] + ratio * (current[1] - previous[1])
    tail = points[-1]
    before_tail = points[-2] if len(points) > 1 else tail
    span = max(tail[0] - before_tail[0], 0.0001)
    slope = (tail[1] - before_tail[1]) / span
    return max(0.2, tail[1] + (mega_pixels - tail[0]) * slope)


def _default_eta_point_for_profile(profile_id: str, mega_pixels: float) -> float:
    points = ETA_BASE_PROFILE_POINTS.get(profile_id) or ETA_BASE_PROFILE_POINTS["h264-source"]
    return _interpolate_eta_points(points, mega_pixels)


def _load_recent_render_samples(limit: int = 3000) -> list[dict[str, Any]]:
    if not RENDER_SAMPLES_FILE.exists():
        return []

    window: deque[dict[str, Any]] = deque(maxlen=limit)
    with RENDER_SAMPLES_FILE.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                window.append(payload)

    return list(window)


def _build_render_eta_calibration(samples: list[dict[str, Any]]) -> dict[str, Any]:
    successful: list[dict[str, Any]] = []
    for sample in samples:
        if not bool(sample.get("success", False)):
            continue
        duration_seconds = _safe_float(sample.get("source_duration_seconds"))
        elapsed_seconds = _safe_float(sample.get("render_elapsed_seconds"))
        if duration_seconds is None or elapsed_seconds is None:
            continue
        if elapsed_seconds > duration_seconds * 240:
            continue

        width = int(sample.get("source_width") or 0)
        height = int(sample.get("source_height") or 0)
        if width < 2 or height < 2:
            continue

        mega_pixels = (width * height) / 1_000_000.0
        if mega_pixels <= 0:
            continue

        wall_x = elapsed_seconds / duration_seconds
        if wall_x <= 0:
            continue

        payload = dict(sample)
        payload["mega_pixels"] = mega_pixels
        payload["wall_x_realtime"] = wall_x
        successful.append(payload)

    profile_points: dict[str, list[dict[str, Any]]] = {}
    profile_ids = sorted({*ETA_BASE_PROFILE_POINTS.keys(), *(str(s.get("render_profile") or "") for s in successful)})
    for profile_id in profile_ids:
        if not profile_id:
            continue

        baseline = ETA_BASE_PROFILE_POINTS.get(profile_id) or ETA_BASE_PROFILE_POINTS["h264-source"]
        anchor_values: dict[float, list[float]] = defaultdict(list)
        profile_samples = [s for s in successful if str(s.get("render_profile") or "") == profile_id]
        preferred = [
            s
            for s in profile_samples
            if str(s.get("fps_mode") or "source_exact") == "source_exact" and not bool(s.get("maps_enabled", False))
        ]
        selected = preferred if len(preferred) >= 2 else profile_samples
        for sample in selected:
            anchor = _nearest_eta_anchor(float(sample["mega_pixels"]))
            anchor_values[anchor].append(float(sample["wall_x_realtime"]))

        points: list[dict[str, Any]] = []
        for anchor, base_x in baseline:
            observations = anchor_values.get(anchor, [])
            measured = _median(observations)
            count = len(observations)
            if measured is None:
                blended = base_x
            else:
                confidence = min(count, 16) / 16.0
                blended = (base_x * (1.0 - confidence)) + (measured * confidence)
            points.append(
                {
                    "mega_pixels": round(anchor, 3),
                    "x_realtime": round(max(blended, 0.2), 4),
                    "sample_count": count,
                }
            )

        profile_points[profile_id] = points

    normalized_by_mode: dict[str, list[float]] = defaultdict(list)
    fixed_points: dict[int, list[float]] = defaultdict(list)
    maps_on: list[float] = []
    maps_off: list[float] = []

    for sample in successful:
        profile_id = str(sample.get("render_profile") or "h264-source")
        mega_pixels = float(sample["mega_pixels"])
        baseline_x = _default_eta_point_for_profile(profile_id, mega_pixels)
        if baseline_x <= 0:
            continue
        normalized = float(sample["wall_x_realtime"]) / baseline_x
        if normalized <= 0:
            continue

        fps_mode = str(sample.get("fps_mode") or "source_exact")
        normalized_by_mode[fps_mode].append(normalized)
        if bool(sample.get("maps_enabled", False)):
            maps_on.append(normalized)
        else:
            maps_off.append(normalized)

        if fps_mode == "fixed":
            fixed_fps_value = _safe_float(sample.get("fixed_fps"))
            if fixed_fps_value is not None:
                fixed_points[int(round(fixed_fps_value))].append(normalized)

    exact_median = _median(normalized_by_mode.get("source_exact", [])) or 1.0
    rounded_median = _median(normalized_by_mode.get("source_rounded", []))
    source_rounded_multiplier = (
        rounded_median / exact_median
        if rounded_median is not None and exact_median > 0
        else ETA_DEFAULT_SOURCE_ROUNDED_MULTIPLIER
    )
    source_rounded_multiplier = max(0.45, min(1.4, source_rounded_multiplier))

    maps_on_median = _median(maps_on)
    maps_off_median = _median(maps_off)
    maps_multiplier = (
        maps_on_median / maps_off_median
        if maps_on_median is not None and maps_off_median is not None and maps_off_median > 0
        else ETA_DEFAULT_MAPS_MULTIPLIER
    )
    maps_multiplier = max(0.7, min(1.5, maps_multiplier))

    fixed_measurements: list[tuple[float, float]] = []
    fixed_series: list[dict[str, Any]] = []
    for fps in sorted(fixed_points):
        median_value = _median(fixed_points[fps])
        if median_value is None or exact_median <= 0:
            continue
        multiplier = median_value / exact_median
        multiplier = max(0.2, min(2.0, multiplier))
        fixed_measurements.append((float(fps), multiplier))
        fixed_series.append({"fps": fps, "multiplier": round(multiplier, 4), "sample_count": len(fixed_points[fps])})

    intercept = ETA_DEFAULT_FIXED_MULTIPLIER_INTERCEPT
    slope = ETA_DEFAULT_FIXED_MULTIPLIER_SLOPE
    if len(fixed_measurements) >= 2:
        x_values = [point[0] for point in fixed_measurements]
        y_values = [point[1] for point in fixed_measurements]
        x_mean = sum(x_values) / len(x_values)
        y_mean = sum(y_values) / len(y_values)
        variance = sum((x - x_mean) ** 2 for x in x_values)
        if variance > 0:
            slope = sum((x - x_mean) * (y - y_mean) for x, y in fixed_measurements) / variance
            intercept = y_mean - slope * x_mean
    elif len(fixed_measurements) == 1:
        fps, multiplier = fixed_measurements[0]
        slope = ETA_DEFAULT_FIXED_MULTIPLIER_SLOPE
        intercept = multiplier - (slope * fps)

    slope = max(0.0, min(0.05, slope))
    intercept = max(0.1, min(1.4, intercept))

    return {
        "version": 1,
        "generated_at": _utc_now(),
        "sample_count": len(successful),
        "profile_points": profile_points,
        "maps_multiplier": round(maps_multiplier, 4),
        "source_rounded_multiplier": round(source_rounded_multiplier, 4),
        "fixed_multiplier_intercept": round(intercept, 4),
        "fixed_multiplier_slope": round(slope, 4),
        "fixed_multiplier_min": ETA_DEFAULT_FIXED_MULTIPLIER_MIN,
        "fixed_samples": fixed_series,
        "defaults": {
            "maps_multiplier": ETA_DEFAULT_MAPS_MULTIPLIER,
            "source_rounded_multiplier": ETA_DEFAULT_SOURCE_ROUNDED_MULTIPLIER,
            "fixed_multiplier_intercept": ETA_DEFAULT_FIXED_MULTIPLIER_INTERCEPT,
            "fixed_multiplier_slope": ETA_DEFAULT_FIXED_MULTIPLIER_SLOPE,
            "fixed_multiplier_min": ETA_DEFAULT_FIXED_MULTIPLIER_MIN,
        },
    }


def _get_render_eta_calibration() -> dict[str, Any]:
    global _RENDER_ETA_CACHE, _RENDER_ETA_CACHE_MTIME

    mtime = RENDER_SAMPLES_FILE.stat().st_mtime if RENDER_SAMPLES_FILE.exists() else -1.0
    with _RENDER_ANALYTICS_LOCK:
        if _RENDER_ETA_CACHE is not None and _RENDER_ETA_CACHE_MTIME == mtime:
            return deepcopy(_RENDER_ETA_CACHE)

        samples = _load_recent_render_samples(limit=3000)
        calibration = _build_render_eta_calibration(samples)
        _RENDER_ETA_CACHE = calibration
        _RENDER_ETA_CACHE_MTIME = mtime
        return deepcopy(calibration)


def _record_render_sample(sample: dict[str, Any]) -> None:
    global _RENDER_ETA_CACHE, _RENDER_ETA_CACHE_MTIME

    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(sample, separators=(",", ":"), ensure_ascii=True)
    with _RENDER_ANALYTICS_LOCK:
        with RENDER_SAMPLES_FILE.open("a", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
        _RENDER_ETA_CACHE = None
        _RENDER_ETA_CACHE_MTIME = None


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
    overlay_size: tuple[int, int] | None = None,
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
        "--cache-dir",
        str(CONFIG_DIR),
        "--profile",
        render_profile,
    ]

    if overlay_size is not None:
        cmd.extend(["--overlay-size", f"{overlay_size[0]}x{overlay_size[1]}"])

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
    return [
        {
            "id": key,
            "label": theme.label,
            "panel_bg": theme.panel_bg,
            "panel_bg_alt": theme.panel_bg_alt,
            "speed_rgb": theme.speed_rgb,
            "accent_rgb": theme.accent_rgb,
            "text_rgb": theme.text_rgb,
        }
        for key, theme in THEMES.items()
    ]


def _layout_style_meta() -> list[dict[str, str]]:
    return [
        {
            "id": key,
            "label": style.label,
            "description": style.description,
        }
        for key, style in LAYOUT_STYLES.items()
    ]


def _component_meta() -> list[dict[str, Any]]:
    return [
        {
            "id": key,
            "label": option.label,
            "description": option.description,
            "default_enabled": option.default_enabled,
        }
        for key, option in COMPONENT_OPTIONS.items()
    ]


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _parse_component_visibility(raw: str | None, include_maps: bool) -> dict[str, bool]:
    payload: dict[str, Any] | None = None
    if not raw:
        visibility = dict(DEFAULT_COMPONENT_VISIBILITY)
    else:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"component_visibility must be valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="component_visibility must be an object")
        payload = parsed

        visibility = dict(DEFAULT_COMPONENT_VISIBILITY)
        for key, value in payload.items():
            if key not in COMPONENT_OPTIONS:
                raise HTTPException(status_code=400, detail=f"Unsupported component option: {key}")
            visibility[key] = _coerce_bool(value)

    # Keep backwards compatibility with the legacy include_maps toggle.
    if payload is not None and "route_maps" in payload:
        return visibility

    visibility["route_maps"] = bool(include_maps)
    return visibility


def _auto_render_profile_candidates(metadata: dict[str, Any]) -> list[str]:
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    high_resolution = width > 3840 or height > 2160

    if sys.platform == "darwin":
        if high_resolution:
            return ["qt-hevc-balanced", "h264-4k-compat", "h264-source", "h264-fast"]
        return ["h264-source", "qt-hevc-balanced", "h264-fast"]

    if high_resolution:
        return ["h264-source", "h264-4k-compat", "h264-fast"]
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


def _to_even(value: int) -> int:
    # Keep dimensions encoder-safe (many codecs expect even dimensions).
    if value < 2:
        return 2
    return value if value % 2 == 0 else value - 1


def _overlay_dimensions_for_profile(metadata: dict[str, Any], profile_id: str) -> tuple[int, int]:
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    if width < 2 or height < 2:
        return 1920, 1080

    if profile_id != "h264-4k-compat" or width <= PROFILE_4K_COMPAT_MAX_WIDTH:
        return width, height

    scaled_height = int(round(height * (PROFILE_4K_COMPAT_MAX_WIDTH / float(width))))
    return _to_even(PROFILE_4K_COMPAT_MAX_WIDTH), _to_even(scaled_height)


def _run_renderer(
    cmd: list[str],
    log_path: Path,
    job_id: str,
    video_index: int,
    total_videos: int,
) -> tuple[int, str, float]:
    progress_re = re.compile(r"\[(\s*\d+)%\]")
    last_line = ""
    started = time.perf_counter()

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
    elapsed_seconds = max(time.perf_counter() - started, 0.0)
    return return_code, last_line, elapsed_seconds


def _normalize_console_line(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value).strip()


def _process_job(job_id: str) -> None:
    job = _get_job(job_id)
    if job.get("status") in TERMINAL_JOB_STATUSES:
        return

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
    try:
        shift_gpx_timestamps(
            source_gpx,
            shifted_gpx,
            float(job["settings"]["gpx_offset_seconds"]),
            speed_unit=str(job["settings"].get("gpx_speed_unit", "auto")),
        )
    except Exception as exc:  # noqa: BLE001
        _set_job(
            job_id,
            status="failed",
            progress=100,
            finished_at=_utc_now(),
            message=f"GPX preparation failed: {exc}",
        )
        return

    if DELETE_INPUTS_ON_COMPLETE:
        _safe_unlink(source_gpx)

    total_videos = len(job["videos"])
    failed_count = 0
    owner_uid = str(job.get("uid") or "")
    first_failure_reason: str | None = None

    for index, video_state in enumerate(job["videos"]):
        input_name = video_state["input_name"]
        input_path = inputs_dir / input_name

        _set_video(job_id, index, status="running", progress=1, detail="Probing metadata")

        try:
            metadata = _probe_video(input_path)
            _set_file_mtime_from_creation(input_path, metadata.get("creation_time"))
            selected_profile, profile_candidates = _select_render_profile(metadata, job["settings"]["render_profile"])
            layout_path = work_dir / f"layout-{index + 1}.xml"
            maps_enabled_for_attempt = bool(job["settings"]["include_maps"])
            map_fallback_used = False

            output_name = f"{Path(input_name).stem}-overlay.mp4"
            output_path = outputs_dir / output_name
            log_path = logs_dir / f"{Path(input_name).stem}.log"

            return_code = 1
            attempted_profile = selected_profile
            last_error: str | None = None
            render_elapsed_seconds = 0.0

            for profile_idx, profile_id in enumerate(profile_candidates):
                attempted_profile = profile_id
                overlay_width, overlay_height = _overlay_dimensions_for_profile(metadata, profile_id)
                overlay_size: tuple[int, int] | None = None
                if overlay_width != int(metadata["width"]) or overlay_height != int(metadata["height"]):
                    overlay_size = (overlay_width, overlay_height)

                layout_xml = render_layout_xml(
                    overlay_width,
                    overlay_height,
                    job["settings"]["overlay_theme"],
                    include_maps=maps_enabled_for_attempt,
                    layout_style=str(job["settings"].get("layout_style", DEFAULT_LAYOUT_STYLE)),
                    component_visibility=job["settings"].get("component_visibility"),
                    speed_units=str(job["settings"].get("speed_units", "kph")),
                )
                layout_path.write_text(layout_xml, encoding="utf-8")

                _set_video(
                    job_id,
                    index,
                    detail=(
                        f"Rendering with {profile_id} ({profile_idx + 1}/{len(profile_candidates)}) "
                        f"at {overlay_width}x{overlay_height}"
                    ),
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
                    overlay_size=overlay_size,
                )
                return_code, last_line, elapsed_seconds = _run_renderer(command, log_path, job_id, index, total_videos)
                render_elapsed_seconds += elapsed_seconds
                normalized_last_line = _normalize_console_line(last_line).lower()
                if (
                    return_code != 0
                    and maps_enabled_for_attempt
                    and not map_fallback_used
                    and "images do not match" in normalized_last_line
                ):
                    map_fallback_used = True
                    maps_enabled_for_attempt = False
                    _set_video(job_id, index, detail="Map rendering failed; retrying without route maps.")
                    fallback_layout = render_layout_xml(
                        overlay_width,
                        overlay_height,
                        job["settings"]["overlay_theme"],
                        include_maps=False,
                        layout_style=str(job["settings"].get("layout_style", DEFAULT_LAYOUT_STYLE)),
                        component_visibility=job["settings"].get("component_visibility"),
                        speed_units=str(job["settings"].get("speed_units", "kph")),
                    )
                    layout_path.write_text(fallback_layout, encoding="utf-8")
                    return_code, last_line, elapsed_seconds = _run_renderer(command, log_path, job_id, index, total_videos)
                    render_elapsed_seconds += elapsed_seconds
                    normalized_last_line = _normalize_console_line(last_line).lower()

                if return_code == 0:
                    selected_profile = attempted_profile
                    break
                if normalized_last_line and ("error" in normalized_last_line or "exception" in normalized_last_line):
                    last_error = normalized_last_line
                else:
                    last_error = f"Renderer exited with code {return_code} using profile {profile_id}"
                # Retry other profiles only for likely codec/encode issues.
                if "don't overlap in time" in normalized_last_line:
                    break

            if return_code != 0:
                failed_count += 1
                if first_failure_reason is None:
                    first_failure_reason = last_error or f"Renderer exited with code {return_code}"
                _set_video(
                    job_id,
                    index,
                    status="failed",
                    progress=0,
                    error=last_error or f"Renderer exited with code {return_code}",
                    log_name=log_path.name,
                    source_resolution=f"{metadata['width']}x{metadata['height']}",
                    source_fps=metadata.get("fps_raw"),
                    source_duration_seconds=metadata.get("duration"),
                    render_elapsed_seconds=round(render_elapsed_seconds, 3),
                    wall_x_realtime=(
                        round(render_elapsed_seconds / float(metadata["duration"]), 5)
                        if metadata.get("duration") and float(metadata["duration"]) > 0
                        else None
                    ),
                    render_profile_label=_render_profile_label(attempted_profile),
                )
                try:
                    _record_render_sample(
                        {
                            "recorded_at": _utc_now(),
                            "job_id": job_id,
                            "video_id": video_state.get("id"),
                            "input_name": input_name,
                            "platform": sys.platform,
                            "success": False,
                            "error": last_error or f"Renderer exited with code {return_code}",
                            "render_profile": attempted_profile,
                            "requested_render_profile": str(job["settings"].get("render_profile", AUTO_RENDER_PROFILE)),
                            "maps_enabled": maps_enabled_for_attempt,
                            "fps_mode": str(job["settings"].get("fps_mode", "source_exact")),
                            "fixed_fps": float(job["settings"].get("fixed_fps", 30.0)),
                            "source_width": metadata.get("width"),
                            "source_height": metadata.get("height"),
                            "source_duration_seconds": metadata.get("duration"),
                            "source_codec": metadata.get("codec"),
                            "source_fps": metadata.get("fps"),
                            "source_fps_raw": metadata.get("fps_raw"),
                            "render_elapsed_seconds": round(render_elapsed_seconds, 3),
                            "wall_x_realtime": (
                                round(render_elapsed_seconds / float(metadata["duration"]), 5)
                                if metadata.get("duration") and float(metadata["duration"]) > 0
                                else None
                            ),
                        }
                    )
                except Exception:  # noqa: BLE001
                    LOGGER.exception("Failed to persist failed render sample for job=%s video=%s", job_id, input_name)
                continue

            upload_metadata = _upload_output_to_r2(
                uid=owner_uid,
                job_id=job_id,
                output_name=output_name,
                output_path=output_path,
            )

            output_metadata: dict[str, Any] | None = None
            try:
                output_metadata = _probe_video(output_path)
            except Exception:  # noqa: BLE001
                output_metadata = None

            _set_video(
                job_id,
                index,
                status="completed",
                progress=100,
                output_name=output_name,
                log_name=log_path.name,
                render_profile=selected_profile,
                render_profile_label=_render_profile_label(selected_profile),
                source_resolution=f"{metadata['width']}x{metadata['height']}",
                source_fps=metadata.get("fps_raw"),
                source_duration_seconds=metadata.get("duration"),
                output_resolution=(
                    f"{output_metadata['width']}x{output_metadata['height']}" if output_metadata else None
                ),
                output_fps=output_metadata.get("fps_raw") if output_metadata else None,
                output_duration_seconds=output_metadata.get("duration") if output_metadata else None,
                output_codec=output_metadata.get("codec") if output_metadata else None,
                render_elapsed_seconds=round(render_elapsed_seconds, 3),
                wall_x_realtime=(
                    round(render_elapsed_seconds / float(metadata["duration"]), 5)
                    if metadata.get("duration") and float(metadata["duration"]) > 0
                    else None
                ),
                error=None,
                **upload_metadata,
            )
            try:
                _record_render_sample(
                    {
                        "recorded_at": _utc_now(),
                        "job_id": job_id,
                        "video_id": video_state.get("id"),
                        "input_name": input_name,
                        "platform": sys.platform,
                        "success": True,
                        "render_profile": selected_profile,
                        "requested_render_profile": str(job["settings"].get("render_profile", AUTO_RENDER_PROFILE)),
                        "maps_enabled": maps_enabled_for_attempt,
                        "fps_mode": str(job["settings"].get("fps_mode", "source_exact")),
                        "fixed_fps": float(job["settings"].get("fixed_fps", 30.0)),
                        "source_width": metadata.get("width"),
                        "source_height": metadata.get("height"),
                        "source_duration_seconds": metadata.get("duration"),
                        "source_codec": metadata.get("codec"),
                        "source_fps": metadata.get("fps"),
                        "source_fps_raw": metadata.get("fps_raw"),
                        "output_width": output_metadata.get("width") if output_metadata else None,
                        "output_height": output_metadata.get("height") if output_metadata else None,
                        "output_duration_seconds": output_metadata.get("duration") if output_metadata else None,
                        "output_codec": output_metadata.get("codec") if output_metadata else None,
                        "output_fps": output_metadata.get("fps") if output_metadata else None,
                        "output_fps_raw": output_metadata.get("fps_raw") if output_metadata else None,
                        "render_elapsed_seconds": round(render_elapsed_seconds, 3),
                        "wall_x_realtime": (
                            round(render_elapsed_seconds / float(metadata["duration"]), 5)
                            if metadata.get("duration") and float(metadata["duration"]) > 0
                            else None
                        ),
                    }
                )
            except Exception:  # noqa: BLE001
                LOGGER.exception("Failed to persist completed render sample for job=%s video=%s", job_id, input_name)
        except Exception as exc:  # noqa: BLE001
            failed_count += 1
            if first_failure_reason is None:
                first_failure_reason = str(exc)
            _set_video(
                job_id,
                index,
                status="failed",
                progress=0,
                error=str(exc),
                detail="Render/upload failed",
            )
        finally:
            if DELETE_INPUTS_ON_COMPLETE:
                _safe_unlink(input_path)

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
        failure_message = "Rendering failed"
        if first_failure_reason:
            failure_message = f"Rendering failed: {first_failure_reason[:240]}"
        _set_job(job_id, status="failed", progress=100, finished_at=_utc_now(), message=failure_message)

    expires_at = _utc_after_hours(JOB_OUTPUT_RETENTION_HOURS)
    _set_job(job_id, expires_at=expires_at)
    _write_expiry_marker(job_dir, expires_at)
    _cleanup_local_artifacts_if_uploaded(job_id)


@app.get("/")
def api_index() -> dict[str, str]:
    return {"name": "POVerlay API", "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    return {
        "themes": sorted(THEMES.keys()),
        "theme_options": _theme_meta(),
        "layout_styles": _layout_style_meta(),
        "default_layout_style": DEFAULT_LAYOUT_STYLE,
        "component_options": _component_meta(),
        "default_component_visibility": DEFAULT_COMPONENT_VISIBILITY,
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
        "render_eta_calibration": _get_render_eta_calibration(),
    }


@app.get("/api/user/settings")
def get_user_settings(uid: str = Depends(_require_user_uid)) -> dict[str, Any]:
    profile = _load_or_create_user_profile(uid)
    return {
        "uid": uid,
        "notifications_enabled": bool(profile.get("notifications_enabled", True)),
    }


@app.put("/api/user/settings")
def update_user_settings(payload: UserSettingsUpdate, uid: str = Depends(_require_user_uid)) -> dict[str, Any]:
    profile = _update_user_notification_preference(uid, notifications_enabled=payload.notifications_enabled)
    return {
        "uid": uid,
        "notifications_enabled": bool(profile.get("notifications_enabled", True)),
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
    layout_style: str = Form(DEFAULT_LAYOUT_STYLE),
    component_visibility: str = Form(""),
    include_maps: bool = Form(True),
    fps_mode: str = Form("source_exact"),
    fixed_fps: float = Form(30.0),
    render_profile: str = Form(AUTO_RENDER_PROFILE),
    uid: str = Depends(_require_user_uid),
) -> dict[str, Any]:
    _require_durable_pipeline_enabled()
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
    if layout_style not in LAYOUT_STYLES:
        raise HTTPException(status_code=400, detail=f"Unsupported layout style: {layout_style}")
    if fps_mode not in ALLOWED_FPS_MODES:
        raise HTTPException(status_code=400, detail=f"Unsupported fps mode: {fps_mode}")
    if fps_mode == "fixed" and fixed_fps <= 0:
        raise HTTPException(status_code=400, detail="fixed_fps must be > 0")
    if render_profile not in ALLOWED_RENDER_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unsupported render_profile: {render_profile}")

    resolved_component_visibility = _parse_component_visibility(component_visibility, include_maps)
    include_maps = bool(resolved_component_visibility.get("route_maps", include_maps))

    renderer_path = Path(GOPRO_DASHBOARD_BIN)
    if not GOPRO_DASHBOARD_BIN.strip() or not renderer_path.is_file():
        raise HTTPException(
            status_code=500,
            detail=(
                f"Renderer binary not found at {GOPRO_DASHBOARD_BIN}. "
                "Set GOPRO_DASHBOARD_BIN or install gopro-overlay in .venv."
            ),
        )

    font_path = Path(DEFAULT_FONT_PATH)
    if not DEFAULT_FONT_PATH.strip() or not font_path.is_file():
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

        input_path = inputs_dir / safe_name
        await _save_upload(video, input_path)
        metadata = await _probe_video_safe(input_path)
        if metadata:
            _set_file_mtime_from_creation(input_path, metadata.get("creation_time"))

        video_states.append(
            {
                "id": uuid4().hex,
                "title": Path(safe_name).stem,
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
                "source_resolution": f"{metadata['width']}x{metadata['height']}" if metadata else None,
                "source_fps": metadata.get("fps_raw") if metadata else None,
                "source_duration_seconds": metadata.get("duration") if metadata else None,
                "output_resolution": None,
                "output_fps": None,
                "output_duration_seconds": None,
                "output_codec": None,
                "render_elapsed_seconds": None,
                "wall_x_realtime": None,
                "r2_object_key": None,
                "r2_bucket": None,
                "r2_etag": None,
                "r2_uploaded_at": None,
            }
        )

    job_data = {
        "id": job_id,
        "uid": uid,
        "job_dir": str(job_dir),
        "status": "queued",
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "expires_at": None,
        "started_at": None,
        "finished_at": None,
        "local_artifacts_deleted_at": None,
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
            "layout_style": layout_style,
            "component_visibility": resolved_component_visibility,
            "include_maps": include_maps,
            "fps_mode": fps_mode,
            "fixed_fps": fixed_fps,
            "render_profile": render_profile,
            "font_path": str(font_path),
        },
    }

    try:
        _persist_job_state(job_data)
    except Exception as exc:  # noqa: BLE001
        _safe_rmtree(job_dir)
        raise HTTPException(status_code=500, detail=f"Failed to persist job state: {exc}") from exc

    _enqueue_job(job_id)

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str, uid: str = Depends(_require_user_uid)) -> dict[str, Any]:
    job = _get_job(job_id, requester_uid=uid)
    outputs_dir = Path(str(job.get("job_dir") or "")) / "outputs"
    has_downloads = False

    for video in job["videos"]:
        output_name = str(video.get("output_name") or "")
        if not output_name:
            video["download_url"] = None
            continue

        if video.get("r2_object_key"):
            video["download_url"] = f"/api/jobs/{job_id}/download/{output_name}"
            has_downloads = True
            continue

        if (outputs_dir / output_name).exists():
            video["download_url"] = f"/api/jobs/{job_id}/download/{output_name}"
            has_downloads = True
        else:
            video["download_url"] = None

    job["download_all_url"] = f"/api/jobs/{job_id}/download-all" if has_downloads else None
    return job


@app.get("/api/media")
def list_media(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MEDIA_LIST_MAX_PAGE_SIZE),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    uid: str = Depends(_require_user_uid),
) -> dict[str, Any]:
    _require_durable_pipeline_enabled()

    if sort_by not in MEDIA_SORT_FIELDS:
        raise HTTPException(status_code=400, detail=f"Unsupported sort_by value: {sort_by}")
    if sort_order not in MEDIA_SORT_ORDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported sort_order value: {sort_order}")

    items: list[dict[str, Any]] = []
    for job in _list_jobs_for_uid(uid):
        normalized_job = _ensure_video_identity_metadata(job)
        for video in normalized_job.get("videos", []):
            if isinstance(video, dict):
                items.append(_build_media_item(normalized_job, video))

    items.sort(key=lambda item: _media_sort_value(item, sort_by), reverse=sort_order == "desc")

    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start_index = (page - 1) * page_size
    paged_items = items[start_index:start_index + page_size]

    return {
        "items": paged_items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }


@app.patch("/api/media/{job_id}/{video_id}")
def rename_media(
    job_id: str,
    video_id: str,
    payload: dict[str, Any] = Body(...),
    uid: str = Depends(_require_user_uid),
) -> dict[str, Any]:
    _require_durable_pipeline_enabled()

    next_title = str(payload.get("title") or "").strip()
    if not next_title:
        raise HTTPException(status_code=400, detail="title is required")
    if len(next_title) > 120:
        raise HTTPException(status_code=400, detail="title must be 120 characters or fewer")

    job = _get_job(job_id, requester_uid=uid)
    job = _ensure_video_identity_metadata(job)
    video_index, video = _find_video_by_id(job, video_id)
    job["videos"][video_index]["title"] = next_title
    updated = _persist_job_state(job)
    _, persisted_video = _find_video_by_id(updated, video_id)

    return {
        "id": str(persisted_video.get("id") or ""),
        "job_id": job_id,
        "title": str(persisted_video.get("title") or next_title),
    }


@app.delete("/api/media/{job_id}/{video_id}")
def delete_media(
    job_id: str,
    video_id: str,
    uid: str = Depends(_require_user_uid),
) -> dict[str, Any]:
    _require_durable_pipeline_enabled()

    job = _get_job(job_id, requester_uid=uid)
    job = _ensure_video_identity_metadata(job)
    video_index, video = _find_video_by_id(job, video_id)

    video_status = str(video.get("status") or "")
    if video_status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Media is still rendering and cannot be deleted")

    object_key = str(video.get("r2_object_key") or "")
    if object_key:
        try:
            _delete_r2_object(object_key)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Failed to delete media object: {exc}") from exc

    job_dir = Path(str(job.get("job_dir") or ""))
    output_name = str(video.get("output_name") or "")
    log_name = str(video.get("log_name") or "")
    if output_name:
        _safe_unlink(job_dir / "outputs" / output_name)
    if log_name:
        _safe_unlink(job_dir / "logs" / log_name)

    del job["videos"][video_index]
    _persist_job_state(job)
    return {"deleted": True, "job_id": job_id, "id": video_id}


@app.post("/api/media/{job_id}/{video_id}/download-link")
def issue_media_download_link(
    job_id: str,
    video_id: str,
    uid: str = Depends(_require_user_uid),
) -> dict[str, Any]:
    _require_durable_pipeline_enabled()

    job = _get_job(job_id, requester_uid=uid)
    job = _ensure_video_identity_metadata(job)
    _, video = _find_video_by_id(job, video_id)

    output_name = str(video.get("output_name") or "")
    object_key = str(video.get("r2_object_key") or "")
    if not output_name or not object_key or str(video.get("status") or "") != "completed":
        raise HTTPException(status_code=404, detail="Media file not available")

    try:
        url = _signed_r2_download_url(object_key, output_name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to sign download URL: {exc}") from exc

    return {
        "url": url,
        "filename": output_name,
        "expires_in_seconds": R2_SIGNED_URL_TTL_SECONDS,
    }


@app.get("/api/jobs/{job_id}/download/{filename}")
def download_output(job_id: str, filename: str, uid: str = Depends(_require_user_uid)) -> Any:
    job = _get_job(job_id, requester_uid=uid)
    video = _find_video_for_filename(job, filename)
    if video is None:
        raise HTTPException(status_code=404, detail="Output file not found")

    object_key = str(video.get("r2_object_key") or "")
    if object_key:
        try:
            signed_url = _signed_r2_download_url(object_key, filename)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Failed to sign download URL: {exc}") from exc
        return RedirectResponse(url=signed_url, status_code=307)

    outputs_dir = (Path(str(job.get("job_dir") or "")) / "outputs").resolve()
    target = (outputs_dir / filename).resolve()
    if outputs_dir not in target.parents or not target.exists():
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(target, filename=target.name, media_type="video/mp4")


@app.get("/api/jobs/{job_id}/log/{filename}")
def download_log(job_id: str, filename: str, uid: str = Depends(_require_user_uid)) -> FileResponse:
    job = _get_job(job_id, requester_uid=uid)
    logs_dir = (Path(str(job.get("job_dir") or "")) / "logs").resolve()
    target = (logs_dir / filename).resolve()

    if logs_dir not in target.parents or not target.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    return FileResponse(target, filename=target.name, media_type="text/plain")


@app.get("/api/jobs/{job_id}/download-all")
def download_all(job_id: str, uid: str = Depends(_require_user_uid)) -> FileResponse:
    job = _get_job(job_id, requester_uid=uid)

    r2_outputs: list[tuple[str, str]] = []
    local_outputs: list[str] = []
    for video in job.get("videos", []):
        output_name = str(video.get("output_name") or "")
        if not output_name:
            continue
        object_key = str(video.get("r2_object_key") or "")
        if object_key:
            r2_outputs.append((output_name, object_key))
        else:
            local_outputs.append(output_name)

    if not r2_outputs and not local_outputs:
        raise HTTPException(status_code=404, detail="No outputs available")

    temp_dir = DATA_DIR / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    zip_path = temp_dir / f"outputs-{job_id}-{uuid4().hex}.zip"

    if r2_outputs:
        _build_zip_from_r2(r2_outputs, zip_path)
    else:
        outputs_dir = Path(str(job.get("job_dir") or "")) / "outputs"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_name in local_outputs:
                source = outputs_dir / file_name
                if source.exists():
                    archive.write(source, arcname=source.name)

    return FileResponse(
        zip_path,
        filename=f"overlay-renders-{job_id}.zip",
        media_type="application/zip",
        background=BackgroundTask(_safe_unlink, zip_path),
    )
