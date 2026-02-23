from __future__ import annotations

from copy import deepcopy
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Ensure the apps/api package root is importable when tests run from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.layouts import DEFAULT_LAYOUT_STYLE, LAYOUT_STYLES, render_layout_xml  # noqa: E402
import app.main as api_main  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)

NEW_LAYOUT_STYLE_IDS = (
    "moto-journey-needle",
    "moto-journey-dual-bars",
    "compass-asi-cluster",
    "power-zone-pro",
)


@pytest.fixture(autouse=True)
def fake_job_store(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, object]]:
    store: dict[str, dict[str, object]] = {}

    def _persist_job_state(job: dict[str, object]) -> dict[str, object]:
        payload = deepcopy(job)
        payload["updated_at"] = payload.get("updated_at") or "2026-01-01T00:00:00+00:00"
        store[str(payload["id"])] = payload
        return deepcopy(payload)

    def _load_job_state(job_id: str, *, prefer_cache: bool) -> dict[str, object] | None:  # noqa: ARG001
        payload = store.get(job_id)
        return deepcopy(payload) if payload is not None else None

    def _list_jobs_with_status(statuses: set[str]) -> list[dict[str, object]]:
        return [deepcopy(job) for job in store.values() if str(job.get("status")) in statuses]

    def _list_jobs_for_uid(uid: str) -> list[dict[str, object]]:
        return [deepcopy(job) for job in store.values() if str(job.get("uid")) == uid]

    monkeypatch.setattr(api_main, "_persist_job_state", _persist_job_state)
    monkeypatch.setattr(api_main, "_load_job_state", _load_job_state)
    monkeypatch.setattr(api_main, "_list_jobs_with_status", _list_jobs_with_status)
    monkeypatch.setattr(api_main, "_list_jobs_for_uid", _list_jobs_for_uid)
    monkeypatch.setattr(api_main, "_enqueue_job", lambda job_id: None)
    monkeypatch.setattr(api_main, "FIRESTORE_ENABLED", True)
    monkeypatch.setattr(api_main, "R2_UPLOAD_ENABLED", True)

    with api_main.JOBS_LOCK:
        api_main.JOBS.clear()

    yield store

    with api_main.JOBS_LOCK:
        api_main.JOBS.clear()


def _stub_verify_token(token: str) -> str:
    if token == "token-user-a":
        return "user-a"
    if token == "token-user-b":
        return "user-b"
    raise HTTPException(status_code=401, detail="Invalid or expired token")


@pytest.mark.parametrize(
    "path",
    [
        "/api/jobs/job-1",
        "/api/jobs/job-1/download/output.mp4",
        "/api/jobs/job-1/log/render.log",
        "/api/jobs/job-1/download-all",
    ],
)
def test_protected_job_get_routes_require_auth(path: str) -> None:
    response = client.get(path)
    assert response.status_code == 401


def test_create_job_requires_auth() -> None:
    files = [
        ("gpx", ("track.gpx", b"<gpx></gpx>", "application/gpx+xml")),
        ("videos", ("clip.mp4", b"fake-video", "video/mp4")),
    ]
    response = client.post("/api/jobs", files=files)
    assert response.status_code == 401


def test_media_routes_require_auth() -> None:
    assert client.get("/api/media").status_code == 401
    assert client.patch("/api/media/job-1/video-1", json={"title": "Renamed"}).status_code == 401
    assert client.delete("/api/media/job-1/video-1").status_code == 401
    assert client.post("/api/media/job-1/video-1/download-link").status_code == 401
    assert client.get("/api/user/access").status_code == 401


def test_invalid_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    response = client.get("/api/jobs/job-1", headers={"Authorization": "Bearer not-valid"})
    assert response.status_code == 401


def test_overlay_dimensions_for_4k_compat_downscale_high_res() -> None:
    assert api_main._overlay_dimensions_for_profile({"width": 5312, "height": 2988}, "h264-4k-compat") == (3840, 2160)


def test_overlay_dimensions_for_non_compat_profile_keep_source() -> None:
    assert api_main._overlay_dimensions_for_profile({"width": 5312, "height": 2988}, "h264-source") == (5312, 2988)


def test_build_renderer_command_sets_cache_dir_and_overlay_size() -> None:
    settings = {
        "font_path": "/tmp/font.ttf",
        "map_style": "osm",
        "speed_units": "mph",
        "altitude_units": "feet",
        "distance_units": "mile",
        "temperature_units": "degF",
        "fps_mode": "source_exact",
        "fixed_fps": 30.0,
    }
    command = api_main._build_renderer_command(
        gpx_path=Path("/tmp/track.gpx"),
        video_path=Path("/tmp/input.mp4"),
        output_path=Path("/tmp/output.mp4"),
        layout_path=Path("/tmp/layout.xml"),
        settings=settings,
        render_profile="h264-4k-compat",
        overlay_size=(3840, 2160),
    )
    assert "--cache-dir" in command
    assert str(api_main.CONFIG_DIR) in command
    assert "--overlay-size" in command
    assert "3840x2160" in command


def test_ffmpeg_profile_presets_include_thread_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "FFMPEG_THREADS_PER_RENDER", 4)
    presets = api_main._ffmpeg_profile_presets()
    assert presets
    for preset in presets.values():
        output = preset.get("output", [])
        assert "-threads" in output
        thread_index = output.index("-threads")
        assert output[thread_index + 1] == "4"


def test_render_eta_calibration_from_samples() -> None:
    samples = [
        {
            "success": True,
            "render_profile": "h264-source",
            "fps_mode": "source_exact",
            "maps_enabled": False,
            "source_width": 1920,
            "source_height": 1080,
            "source_duration_seconds": 10.0,
            "render_elapsed_seconds": 12.0,
        },
        {
            "success": True,
            "render_profile": "h264-source",
            "fps_mode": "source_exact",
            "maps_enabled": False,
            "source_width": 3840,
            "source_height": 2160,
            "source_duration_seconds": 10.0,
            "render_elapsed_seconds": 36.0,
        },
        {
            "success": True,
            "render_profile": "h264-source",
            "fps_mode": "source_rounded",
            "maps_enabled": False,
            "source_width": 1920,
            "source_height": 1080,
            "source_duration_seconds": 10.0,
            "render_elapsed_seconds": 10.5,
        },
    ]

    calibration = api_main._build_render_eta_calibration(samples)
    assert calibration["sample_count"] == 3
    assert calibration["version"] == 1
    assert "h264-source" in calibration["profile_points"]
    assert len(calibration["profile_points"]["h264-source"]) >= 3
    assert calibration["source_rounded_multiplier"] < 1.0


def test_cross_user_job_access_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    job_dir = tmp_path / "job-1"
    job_dir.mkdir(parents=True, exist_ok=True)

    fake_job_store["job-1"] = {
        "id": "job-1",
        "uid": "user-a",
        "job_dir": str(job_dir),
        "videos": [],
        "status": "queued",
    }

    other_user_response = client.get("/api/jobs/job-1", headers={"Authorization": "Bearer token-user-b"})
    assert other_user_response.status_code == 404
    assert other_user_response.json()["detail"] == "Job not found"

    owner_response = client.get("/api/jobs/job-1", headers={"Authorization": "Bearer token-user-a"})
    assert owner_response.status_code == 200
    assert owner_response.json()["uid"] == "user-a"


def test_create_job_persists_authenticated_uid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "_ensure_ffmpeg_profiles", lambda: None)
    monkeypatch.setattr(api_main, "GOPRO_DASHBOARD_BIN", str(Path(__file__).resolve()))
    monkeypatch.setattr(api_main, "DEFAULT_FONT_PATH", str(Path(__file__).resolve()))
    monkeypatch.setattr(api_main, "JOBS_DIR", tmp_path / "jobs")

    async def _noop_save_upload(upload, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"test")
        await upload.close()

    monkeypatch.setattr(api_main, "_save_upload", _noop_save_upload)
    async def _mock_probe_video_safe(_path: Path) -> dict[str, object]:
        return {
            "width": 5312,
            "height": 2988,
            "duration": 42.5,
            "creation_time": "2026-02-07T22:28:39Z",
            "codec": "h264",
            "fps": 29.97,
            "fps_raw": "30000/1001",
        }

    monkeypatch.setattr(api_main, "_probe_video_safe", _mock_probe_video_safe)

    files = [
        ("gpx", ("track.gpx", b"<gpx></gpx>", "application/gpx+xml")),
        ("videos", ("clip.mp4", b"fake-video", "video/mp4")),
    ]
    response = client.post("/api/jobs", files=files, headers={"Authorization": "Bearer token-user-a"})
    assert response.status_code == 200

    job_id = response.json()["job_id"]
    assert fake_job_store[job_id]["uid"] == "user-a"
    first_video = fake_job_store[job_id]["videos"][0]
    assert first_video["source_resolution"] == "5312x2988"
    assert first_video["source_fps"] == "30000/1001"
    assert first_video["source_duration_seconds"] == 42.5


def test_recover_pending_jobs_normalizes_running_states_and_enqueues(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(api_main, "_enqueue_job", lambda job_id: enqueued.append(job_id))

    job_dir = tmp_path / "job-recover"
    inputs_dir = job_dir / "inputs"
    outputs_dir = job_dir / "outputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (inputs_dir / "track.gpx").write_text("<gpx></gpx>")
    (inputs_dir / "clip-running.mp4").write_bytes(b"running")
    (inputs_dir / "clip-failed.mp4").write_bytes(b"failed")
    (inputs_dir / "clip-queued.mp4").write_bytes(b"queued")

    fake_job_store["job-recover"] = {
        "id": "job-recover",
        "uid": "user-a",
        "job_dir": str(job_dir),
        "gpx_name": "track.gpx",
        "status": "running",
        "progress": 42,
        "videos": [
            {"id": "v1", "input_name": "clip-completed.mp4", "status": "completed", "output_name": "clip-completed-overlay.mp4", "r2_object_key": "users/u/jobs/j/outputs/clip-completed-overlay.mp4", "error": None},
            {"id": "v2", "input_name": "clip-running.mp4", "status": "running", "output_name": None, "r2_object_key": None, "error": None},
            {"id": "v3", "input_name": "clip-failed.mp4", "status": "failed", "output_name": None, "r2_object_key": None, "error": "boom"},
            {"id": "v4", "input_name": "clip-queued.mp4", "status": "queued", "output_name": None, "r2_object_key": None, "error": None},
        ],
    }

    api_main._recover_pending_jobs()

    recovered = fake_job_store["job-recover"]
    assert recovered["status"] == "queued"
    assert "Resuming after API restart" in str(recovered["message"])
    statuses = [video["status"] for video in recovered["videos"]]
    assert statuses == ["completed", "queued", "queued", "queued"]
    assert recovered["videos"][2]["error"] is None
    assert enqueued == ["job-recover"]


def test_recover_pending_jobs_marks_missing_artifacts_failed(
    monkeypatch: pytest.MonkeyPatch,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    enqueued: list[str] = []
    monkeypatch.setattr(api_main, "_enqueue_job", lambda job_id: enqueued.append(job_id))

    fake_job_store["job-missing"] = {
        "id": "job-missing",
        "uid": "user-a",
        "job_dir": "/tmp/does-not-exist-queue-job",
        "gpx_name": "track.gpx",
        "status": "queued",
        "progress": 0,
        "videos": [],
    }

    api_main._recover_pending_jobs()

    stale = fake_job_store["job-missing"]
    assert stale["status"] == "failed"
    assert stale["progress"] == 100
    assert "missing on disk" in str(stale["message"])
    assert enqueued == []


def test_process_job_resume_skips_already_completed_videos(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    job_id = "job-resume"
    job_dir = tmp_path / job_id
    inputs_dir = job_dir / "inputs"
    outputs_dir = job_dir / "outputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (inputs_dir / "track.gpx").write_text("<gpx></gpx>")
    (inputs_dir / "pending.mp4").write_bytes(b"pending-video")

    fake_job_store[job_id] = {
        "id": job_id,
        "uid": "user-a",
        "job_dir": str(job_dir),
        "gpx_name": "track.gpx",
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "videos": [
            {
                "id": "video-complete",
                "input_name": "already-done.mp4",
                "status": "completed",
                "progress": 100,
                "output_name": "already-done-overlay.mp4",
                "r2_object_key": "users/user-a/jobs/job-resume/outputs/already-done-overlay.mp4",
            },
            {
                "id": "video-pending",
                "input_name": "pending.mp4",
                "status": "queued",
                "progress": 0,
                "output_name": None,
                "r2_object_key": None,
            },
        ],
        "settings": {
            "gpx_offset_seconds": 0.0,
            "gpx_speed_unit": "auto",
            "render_profile": "h264-fast",
            "overlay_theme": "powder-neon",
            "layout_style": DEFAULT_LAYOUT_STYLE,
            "component_visibility": {},
            "speed_units": "kph",
            "include_maps": False,
            "map_style": "osm",
            "altitude_units": "metre",
            "distance_units": "km",
            "temperature_units": "degC",
            "fps_mode": "source_exact",
            "fixed_fps": 30.0,
            "font_path": str(Path(__file__).resolve()),
        },
    }

    monkeypatch.setattr(api_main, "shift_gpx_timestamps", lambda src, dst, _offset, speed_unit="auto": dst.write_text("<gpx></gpx>"))
    monkeypatch.setattr(
        api_main,
        "_probe_video",
        lambda _path: {
            "width": 1920,
            "height": 1080,
            "duration": 10.0,
            "creation_time": "2026-01-01T00:00:00+00:00",
            "codec": "h264",
            "fps": 30.0,
            "fps_raw": "30/1",
        },
    )
    monkeypatch.setattr(api_main, "_set_file_mtime_from_creation", lambda _path, _creation_time: None)
    monkeypatch.setattr(api_main, "_select_render_profile", lambda _metadata, _requested: ("h264-fast", ["h264-fast"]))
    monkeypatch.setattr(api_main, "_build_renderer_command", lambda **_kwargs: ["renderer"])

    render_calls: list[int] = []

    def _fake_run_renderer(
        _cmd: list[str],
        _log_path: Path,
        _job_id: str,
        video_index: int,
        _completed_before: int,
        _total_videos: int,
    ) -> tuple[int, str, float]:
        render_calls.append(video_index)
        return 0, "[100%]", 1.0

    monkeypatch.setattr(api_main, "_run_renderer", _fake_run_renderer)
    monkeypatch.setattr(
        api_main,
        "_upload_output_to_r2",
        lambda **_kwargs: {
            "r2_object_key": "users/user-a/jobs/job-resume/outputs/pending-overlay.mp4",
            "r2_bucket": "test",
            "r2_etag": "etag",
            "r2_uploaded_at": "2026-01-01T00:00:00+00:00",
            "output_size_bytes": 1,
        },
    )
    monkeypatch.setattr(api_main, "_record_render_sample", lambda _sample: None)
    monkeypatch.setattr(api_main, "_cleanup_local_artifacts_if_uploaded", lambda _job_id: None)

    api_main._process_job(job_id)

    updated = fake_job_store[job_id]
    assert render_calls == [1]
    assert updated["videos"][0]["status"] == "completed"
    assert updated["videos"][1]["status"] == "completed"
    assert updated["status"] == "completed"
    assert (inputs_dir / "track.gpx").exists()
    assert (inputs_dir / "pending.mp4").exists()


def test_set_job_terminal_transition_triggers_single_notification(
    monkeypatch: pytest.MonkeyPatch,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    notifications: list[dict[str, object]] = []
    monkeypatch.setattr(api_main, "_send_job_completion_notification", lambda job: notifications.append(deepcopy(job)))

    fake_job_store["job-terminal"] = {
        "id": "job-terminal",
        "uid": "user-a",
        "job_dir": "/tmp/job-terminal",
        "videos": [],
        "status": "running",
        "progress": 40,
        "message": "Rendering",
    }

    api_main._set_job("job-terminal", status="completed", progress=100, message="Done")
    api_main._set_job("job-terminal", status="completed", progress=100, message="Done")

    assert len(notifications) == 1
    assert notifications[0]["status"] == "completed"


def test_set_job_notification_failure_does_not_block_state_update(
    monkeypatch: pytest.MonkeyPatch,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    monkeypatch.setattr(api_main, "_send_job_completion_notification", lambda _job: (_ for _ in ()).throw(RuntimeError("boom")))

    fake_job_store["job-notify-fail"] = {
        "id": "job-notify-fail",
        "uid": "user-a",
        "job_dir": "/tmp/job-notify-fail",
        "videos": [],
        "status": "running",
        "progress": 60,
        "message": "Rendering",
    }

    api_main._set_job("job-notify-fail", status="failed", progress=100, message="Failed")
    assert fake_job_store["job-notify-fail"]["status"] == "failed"
    assert fake_job_store["job-notify-fail"]["progress"] == 100


def test_user_settings_defaults_to_notifications_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "_load_or_create_user_profile", lambda uid: {"uid": uid, "notifications_enabled": True})

    response = client.get("/api/user/settings", headers={"Authorization": "Bearer token-user-a"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["uid"] == "user-a"
    assert payload["notifications_enabled"] is True


def test_user_settings_update_persists_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(
        api_main,
        "_update_user_notification_preference",
        lambda uid, *, notifications_enabled: {"uid": uid, "notifications_enabled": notifications_enabled},
    )

    response = client.put(
        "/api/user/settings",
        headers={"Authorization": "Bearer token-user-a"},
        json={"notifications_enabled": False},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["uid"] == "user-a"
    assert payload["notifications_enabled"] is False


def test_user_access_reflects_admin_membership(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "ADMIN_UIDS", {"user-a"})

    owner = client.get("/api/user/access", headers={"Authorization": "Bearer token-user-a"})
    assert owner.status_code == 200
    owner_payload = owner.json()
    assert owner_payload["uid"] == "user-a"
    assert owner_payload["admin_configured"] is True
    assert owner_payload["is_admin"] is True

    other = client.get("/api/user/access", headers={"Authorization": "Bearer token-user-b"})
    assert other.status_code == 200
    other_payload = other.json()
    assert other_payload["uid"] == "user-b"
    assert other_payload["admin_configured"] is True
    assert other_payload["is_admin"] is False


def test_admin_overview_requires_admin_uid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "ADMIN_UIDS", {"user-a"})

    denied = client.get("/api/admin/ops/overview", headers={"Authorization": "Bearer token-user-b"})
    assert denied.status_code == 403

    allowed = client.get("/api/admin/ops/overview", headers={"Authorization": "Bearer token-user-a"})
    assert allowed.status_code == 200
    payload = allowed.json()
    assert "queue" in payload
    assert "disk" in payload
    assert "ops" in payload
    assert "pending_jobs" in payload


def test_admin_requeue_job_resets_pending_and_enqueues(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "ADMIN_UIDS", {"user-a"})
    enqueued: list[str] = []
    monkeypatch.setattr(api_main, "_enqueue_job", lambda job_id: enqueued.append(job_id) or True)

    job_dir = tmp_path / "job-admin-requeue"
    inputs_dir = job_dir / "inputs"
    outputs_dir = job_dir / "outputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (inputs_dir / "track.gpx").write_text("<gpx></gpx>")
    (inputs_dir / "pending.mp4").write_bytes(b"pending")

    fake_job_store["job-admin-requeue"] = {
        "id": "job-admin-requeue",
        "uid": "user-a",
        "job_dir": str(job_dir),
        "gpx_name": "track.gpx",
        "status": "failed",
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T01:00:00+00:00",
        "progress": 100,
        "message": "Render failed",
        "videos": [
            {
                "id": "video-1",
                "input_name": "done.mp4",
                "status": "completed",
                "progress": 100,
                "output_name": "done-overlay.mp4",
                "r2_object_key": "users/user-a/jobs/job-admin-requeue/outputs/done-overlay.mp4",
            },
            {
                "id": "video-2",
                "input_name": "pending.mp4",
                "status": "failed",
                "progress": 0,
                "error": "boom",
                "output_name": None,
                "r2_object_key": None,
            },
        ],
    }

    response = client.post(
        "/api/admin/jobs/job-admin-requeue/requeue",
        headers={"Authorization": "Bearer token-user-a"},
        json={"reset_failed_videos": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert enqueued == ["job-admin-requeue"]

    persisted = fake_job_store["job-admin-requeue"]
    assert persisted["status"] == "queued"
    assert persisted["finished_at"] is None
    pending_video = persisted["videos"][1]
    assert pending_video["status"] == "queued"
    assert pending_video["error"] is None


def test_admin_cleanup_endpoint_invokes_cleanup_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "ADMIN_UIDS", {"user-a"})
    monkeypatch.setattr(
        api_main,
        "_run_cleanup_cycle",
        lambda *, include_database, force_database=False: {
            "disk": {"deleted_dirs": 3, "scanned_dirs": 10},
            "database": {"deleted_docs": 2} if include_database and force_database else None,
        },
    )

    response = client.post(
        "/api/admin/ops/cleanup",
        headers={"Authorization": "Bearer token-user-a"},
        json={"include_database": True, "force_database": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["summary"]["disk"]["deleted_dirs"] == 3
    assert payload["summary"]["database"]["deleted_docs"] == 2


def test_admin_cancel_job_marks_pending_videos_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "ADMIN_UIDS", {"user-a"})

    job_dir = tmp_path / "job-admin-cancel"
    (job_dir / "inputs").mkdir(parents=True, exist_ok=True)
    (job_dir / "inputs" / "track.gpx").write_text("<gpx></gpx>")

    fake_job_store["job-admin-cancel"] = {
        "id": "job-admin-cancel",
        "uid": "user-a",
        "job_dir": str(job_dir),
        "gpx_name": "track.gpx",
        "status": "queued",
        "progress": 10,
        "message": "Queued",
        "videos": [
            {"id": "v1", "input_name": "a.mp4", "status": "queued", "progress": 0},
            {"id": "v2", "input_name": "b.mp4", "status": "running", "progress": 25},
            {"id": "v3", "input_name": "c.mp4", "status": "completed", "progress": 100, "output_name": "c-overlay.mp4", "r2_object_key": "users/u/jobs/j/outputs/c-overlay.mp4"},
        ],
    }

    response = client.post(
        "/api/admin/jobs/job-admin-cancel/cancel",
        headers={"Authorization": "Bearer token-user-a"},
        json={"reason": "queue maintenance"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert "Cancelled by admin" in payload["message"]

    persisted = fake_job_store["job-admin-cancel"]
    assert persisted["status"] == "failed"
    assert persisted["progress"] == 100
    assert persisted["videos"][0]["status"] == "failed"
    assert persisted["videos"][1]["status"] == "failed"
    assert persisted["videos"][2]["status"] == "completed"


def test_download_output_redirects_to_signed_r2_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "_signed_r2_download_url", lambda object_key, filename: f"https://signed/{object_key}/{filename}")

    job_dir = tmp_path / "job-2"
    job_dir.mkdir(parents=True, exist_ok=True)
    fake_job_store["job-2"] = {
        "id": "job-2",
        "uid": "user-a",
        "job_dir": str(job_dir),
        "status": "completed",
        "videos": [
            {
                "output_name": "clip-overlay.mp4",
                "r2_object_key": "users/user-a/jobs/job-2/outputs/clip-overlay.mp4",
            }
        ],
    }

    response = client.get(
        "/api/jobs/job-2/download/clip-overlay.mp4",
        headers={"Authorization": "Bearer token-user-a"},
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert response.headers["location"].endswith("/users/user-a/jobs/job-2/outputs/clip-overlay.mp4/clip-overlay.mp4")


def test_media_list_is_user_scoped_with_sorting_and_pagination(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)

    job_a_1 = tmp_path / "job-a-1"
    job_a_1.mkdir(parents=True, exist_ok=True)
    job_a_2 = tmp_path / "job-a-2"
    job_a_2.mkdir(parents=True, exist_ok=True)
    job_b_1 = tmp_path / "job-b-1"
    job_b_1.mkdir(parents=True, exist_ok=True)

    fake_job_store["job-a-1"] = {
        "id": "job-a-1",
        "uid": "user-a",
        "job_dir": str(job_a_1),
        "status": "running",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "videos": [
            {"id": "video-a1", "input_name": "alpha.mp4", "title": "Alpha", "status": "completed", "output_name": "alpha-overlay.mp4", "r2_object_key": "users/user-a/jobs/job-a-1/outputs/alpha-overlay.mp4"},
            {"id": "video-a2", "input_name": "bravo.mp4", "title": "Bravo", "status": "running", "output_name": None, "r2_object_key": None},
        ],
    }
    fake_job_store["job-a-2"] = {
        "id": "job-a-2",
        "uid": "user-a",
        "job_dir": str(job_a_2),
        "status": "failed",
        "created_at": "2026-01-02T00:00:00+00:00",
        "updated_at": "2026-01-02T00:00:00+00:00",
        "videos": [
            {"id": "video-a3", "input_name": "charlie.mp4", "title": "Charlie", "status": "failed", "output_name": None, "r2_object_key": None},
        ],
    }
    fake_job_store["job-b-1"] = {
        "id": "job-b-1",
        "uid": "user-b",
        "job_dir": str(job_b_1),
        "status": "completed",
        "created_at": "2026-01-03T00:00:00+00:00",
        "updated_at": "2026-01-03T00:00:00+00:00",
        "videos": [
            {"id": "video-b1", "input_name": "delta.mp4", "title": "Delta", "status": "completed", "output_name": "delta-overlay.mp4", "r2_object_key": "users/user-b/jobs/job-b-1/outputs/delta-overlay.mp4"},
        ],
    }

    response = client.get(
        "/api/media?page=1&page_size=2&sort_by=title&sort_order=asc",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["total_pages"] == 2
    assert [item["title"] for item in payload["items"]] == ["Alpha", "Bravo"]
    assert {item["job_id"] for item in payload["items"]} <= {"job-a-1", "job-a-2"}


def test_media_rename_updates_title_and_blocks_cross_user(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    job_dir = tmp_path / "job-rename"
    job_dir.mkdir(parents=True, exist_ok=True)

    fake_job_store["job-rename"] = {
        "id": "job-rename",
        "uid": "user-a",
        "job_dir": str(job_dir),
        "status": "completed",
        "videos": [{"id": "video-rename", "input_name": "clip.mp4", "title": "Old title", "status": "completed", "output_name": "clip-overlay.mp4", "r2_object_key": "users/user-a/jobs/job-rename/outputs/clip-overlay.mp4"}],
    }

    owner_response = client.patch(
        "/api/media/job-rename/video-rename",
        json={"title": "New title"},
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert owner_response.status_code == 200
    assert owner_response.json()["title"] == "New title"
    assert fake_job_store["job-rename"]["videos"][0]["title"] == "New title"

    other_response = client.patch(
        "/api/media/job-rename/video-rename",
        json={"title": "Should fail"},
        headers={"Authorization": "Bearer token-user-b"},
    )
    assert other_response.status_code == 404


def test_media_delete_removes_video_and_r2_object(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    deleted_keys: list[tuple[str, str]] = []

    class FakeR2Client:
        def delete_object(self, Bucket: str, Key: str) -> dict[str, object]:  # noqa: N803
            deleted_keys.append((Bucket, Key))
            return {}

    monkeypatch.setattr(api_main, "_r2_client", lambda: FakeR2Client())
    monkeypatch.setattr(api_main, "R2_BUCKET", "test-bucket")

    job_dir = tmp_path / "job-delete"
    (job_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (job_dir / "logs").mkdir(parents=True, exist_ok=True)
    (job_dir / "outputs" / "clip-overlay.mp4").write_bytes(b"video")
    (job_dir / "logs" / "clip.log").write_text("log")

    fake_job_store["job-delete"] = {
        "id": "job-delete",
        "uid": "user-a",
        "job_dir": str(job_dir),
        "status": "completed",
        "videos": [
            {
                "id": "video-delete",
                "input_name": "clip.mp4",
                "title": "Clip",
                "status": "completed",
                "output_name": "clip-overlay.mp4",
                "log_name": "clip.log",
                "r2_object_key": "users/user-a/jobs/job-delete/outputs/clip-overlay.mp4",
            }
        ],
    }

    response = client.delete(
        "/api/media/job-delete/video-delete",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert deleted_keys == [("test-bucket", "users/user-a/jobs/job-delete/outputs/clip-overlay.mp4")]
    assert fake_job_store["job-delete"]["videos"] == []


def test_media_download_link_is_owner_scoped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_job_store: dict[str, dict[str, object]],
) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(
        api_main,
        "_signed_r2_download_url",
        lambda object_key, filename: f"https://signed.example/{object_key}/{filename}",
    )

    job_dir = tmp_path / "job-download-link"
    job_dir.mkdir(parents=True, exist_ok=True)
    fake_job_store["job-download-link"] = {
        "id": "job-download-link",
        "uid": "user-a",
        "job_dir": str(job_dir),
        "status": "completed",
        "videos": [
            {
                "id": "video-link",
                "input_name": "clip.mp4",
                "title": "Clip",
                "status": "completed",
                "output_name": "clip-overlay.mp4",
                "r2_object_key": "users/user-a/jobs/job-download-link/outputs/clip-overlay.mp4",
            }
        ],
    }

    owner_response = client.post(
        "/api/media/job-download-link/video-link/download-link",
        headers={"Authorization": "Bearer token-user-a"},
    )
    assert owner_response.status_code == 200
    payload = owner_response.json()
    assert payload["filename"] == "clip-overlay.mp4"
    assert payload["url"].endswith("/users/user-a/jobs/job-download-link/outputs/clip-overlay.mp4/clip-overlay.mp4")

    other_response = client.post(
        "/api/media/job-download-link/video-link/download-link",
        headers={"Authorization": "Bearer token-user-b"},
    )
    assert other_response.status_code == 404


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ensure_dirs_routes_temp_spooling_to_data_tmp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(api_main, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(api_main, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(api_main, "TEMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(api_main.tempfile, "tempdir", None)

    monkeypatch.delenv("TMPDIR", raising=False)
    monkeypatch.delenv("TMP", raising=False)
    monkeypatch.delenv("TEMP", raising=False)

    api_main._ensure_dirs()

    expected_tmp = str(tmp_path / "tmp")
    assert (tmp_path / "jobs").is_dir()
    assert (tmp_path / "config").is_dir()
    assert (tmp_path / "tmp").is_dir()
    assert api_main.tempfile.gettempdir() == expected_tmp
    assert os.environ["TMPDIR"] == expected_tmp
    assert os.environ["TMP"] == expected_tmp
    assert os.environ["TEMP"] == expected_tmp


def test_meta_contains_expected_top_level_fields() -> None:
    response = client.get("/api/meta")
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload.get("theme_options"), list)
    assert isinstance(payload.get("layout_styles"), list)
    assert isinstance(payload.get("component_options"), list)
    assert isinstance(payload.get("render_profiles"), list)
    assert payload.get("default_render_profile")


def test_meta_layout_styles_match_registry_and_include_new_ids() -> None:
    response = client.get("/api/meta")
    assert response.status_code == 200

    payload = response.json()
    layout_styles = payload.get("layout_styles")
    assert isinstance(layout_styles, list)

    layout_style_ids = [item.get("id") for item in layout_styles if isinstance(item, dict)]
    assert layout_style_ids == list(LAYOUT_STYLES.keys())
    assert payload.get("default_layout_style") == DEFAULT_LAYOUT_STYLE
    for style_id in NEW_LAYOUT_STYLE_IDS:
        assert style_id in layout_style_ids


@pytest.mark.parametrize(
    ("layout_style", "expected_markers"),
    [
        ("moto-journey-needle", ('type="msi"', 'type="moving_journey_map"', 'type="chart"')),
        ("moto-journey-dual-bars", ('type="msi2"', 'type="moving_journey_map"', 'type="chart"')),
        ("compass-asi-cluster", ('type="compass"', 'type="asi"', 'type="journey_map"')),
        ("power-zone-pro", ('type="zone-bar"', 'type="gradient_chart"', 'type="journey_map"')),
    ],
)
def test_render_layout_xml_for_new_styles_contains_expected_widgets(
    layout_style: str,
    expected_markers: tuple[str, str, str],
) -> None:
    layout_xml = render_layout_xml(
        width=1920,
        height=1080,
        theme_name="powder-neon",
        layout_style=layout_style,
        include_maps=True,
    )
    assert layout_xml.startswith("<layout>\n")
    assert layout_xml.endswith("</layout>\n")
    for marker in expected_markers:
        assert marker in layout_xml


def test_layout_preview_manifest_covers_all_layout_styles() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    manifest_path = repo_root / "apps/web/public/layout-previews/manifest.json"
    manifest_payload = json.loads(manifest_path.read_text())
    assert isinstance(manifest_payload, dict)

    layout_ids = manifest_payload.get("layout_ids")
    images = manifest_payload.get("images")

    assert layout_ids == list(LAYOUT_STYLES.keys())
    assert isinstance(images, dict)
    assert set(images) == set(LAYOUT_STYLES.keys())

    web_public = repo_root / "apps/web/public"
    for style_id, image_path in images.items():
        assert isinstance(style_id, str) and style_id
        assert isinstance(image_path, str) and image_path
        resolved = web_public / image_path.lstrip("/")
        assert resolved.suffix == ".png"
        assert resolved.is_file()


def test_studio_page_uses_manifest_mapping_with_svg_fallback() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    studio_page = (repo_root / "apps/web/app/studio/page.tsx").read_text()

    assert 'fetch("/layout-previews/manifest.json")' in studio_page
    assert "setLayoutPreviewById(manifest.images)" in studio_page
    assert "setBrokenLayoutPreviews((prev) => (" in studio_page
    assert "getLayoutPreviewSvg(layoutStyle.id)" in studio_page
