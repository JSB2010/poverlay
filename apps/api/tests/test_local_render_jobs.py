from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as api_main  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)


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

    monkeypatch.setattr(api_main, "_persist_job_state", _persist_job_state)
    monkeypatch.setattr(api_main, "_load_job_state", _load_job_state)
    monkeypatch.setattr(api_main, "FIRESTORE_ENABLED", True)
    monkeypatch.setattr(api_main, "R2_UPLOAD_ENABLED", False)
    monkeypatch.setattr(api_main, "LOCAL_RENDER_ENABLED", True)

    with api_main.JOBS_LOCK:
        api_main.JOBS.clear()
    with api_main.LOCAL_RENDER_LOCK:
        api_main.LOCAL_RENDER_PAIRINGS.clear()
        api_main.LOCAL_RENDER_WORKER_SESSIONS.clear()

    yield store

    with api_main.JOBS_LOCK:
        api_main.JOBS.clear()
    with api_main.LOCAL_RENDER_LOCK:
        api_main.LOCAL_RENDER_PAIRINGS.clear()
        api_main.LOCAL_RENDER_WORKER_SESSIONS.clear()


def _stub_verify_token(token: str) -> str:
    if token == "token-user-a":
        return "user-a"
    if token == "token-user-b":
        return "user-b"
    raise HTTPException(status_code=401, detail="Invalid or expired token")


def _auth(uid: str = "user-a") -> dict[str, str]:
    token = "token-user-a" if uid == "user-a" else "token-user-b"
    return {"Authorization": f"Bearer {token}"}


def _local_job_payload() -> dict[str, object]:
    return {
        "gpx_name": "track.gpx",
        "videos": [
            {
                "input_name": "clip.mp4",
                "title": "Clip",
                "size_bytes": 1234,
                "source_resolution": "1920x1080",
                "source_fps": "30000/1001",
                "source_duration_seconds": 12.5,
                "local_input_path": "/Users/test/clip.mp4",
            }
        ],
        "settings": {
            "overlay_theme": "powder-neon",
            "layout_style": api_main.DEFAULT_LAYOUT_STYLE,
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
            "component_visibility": dict(api_main.DEFAULT_COMPONENT_VISIBILITY),
            "include_maps": True,
        },
        "upload_intent": "local_only",
        "local_output_dir": "/Users/test/POVerlay",
    }


def _media_library_job_payload() -> dict[str, object]:
    payload = _local_job_payload()
    payload["upload_intent"] = "media_library"
    return payload


def _paired_worker_token(monkeypatch: pytest.MonkeyPatch, uid: str = "user-a") -> str:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    start_response = client.post("/api/local-render/pairing/start", headers=_auth(uid))
    assert start_response.status_code == 200
    pairing_code = start_response.json()["pairing_code"]
    complete_response = client.post(
        "/api/local-render/pairing/complete",
        json={"pairing_code": pairing_code, "worker_version": "0.1.0", "worker_platform": "darwin-arm64"},
    )
    assert complete_response.status_code == 200
    return str(complete_response.json()["worker_token"])


def test_local_render_routes_require_auth() -> None:
    assert client.post("/api/local-render/pairing/start").status_code == 401
    assert client.post("/api/local-render/jobs", json=_local_job_payload()).status_code == 401
    assert client.patch("/api/local-render/jobs/job-1", json={"status": "local_running"}).status_code == 401


def test_local_render_requires_feature_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "LOCAL_RENDER_ENABLED", False)

    response = client.post("/api/local-render/pairing/start", headers=_auth())

    assert response.status_code == 503


def test_local_smoke_auth_and_memory_jobs_allow_local_render_without_firestore_or_firebase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_main, "FIREBASE_AUTH_ENABLED", False)
    monkeypatch.setattr(api_main, "FIRESTORE_ENABLED", False)
    monkeypatch.setattr(api_main, "LOCAL_RENDER_ENABLED", True)
    monkeypatch.setattr(api_main, "LOCAL_SMOKE_AUTH_UID", "smoke-user")
    monkeypatch.setattr(api_main, "LOCAL_SMOKE_IN_MEMORY_JOBS", True)

    response = client.post("/api/local-render/jobs", json=_local_job_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["uid"] == "smoke-user"
    loaded = api_main._load_job_state(payload["id"], prefer_cache=False)
    assert loaded is not None
    assert loaded["uid"] == "smoke-user"


def test_pairing_code_is_single_use(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)

    start_response = client.post("/api/local-render/pairing/start", headers=_auth())
    assert start_response.status_code == 200
    payload = start_response.json()
    assert payload["desktop_deep_link"].startswith("poverlay://connect?pairing_code=")

    complete_response = client.post(
        "/api/local-render/pairing/complete",
        json={"pairing_code": payload["pairing_code"], "worker_version": "0.1.0", "worker_platform": "win32-x64"},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["uid"] == "user-a"
    assert complete_response.json()["worker_token"]

    second_response = client.post(
        "/api/local-render/pairing/complete",
        json={"pairing_code": payload["pairing_code"]},
    )
    assert second_response.status_code == 404


def test_create_local_render_job_does_not_enqueue_or_require_r2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)

    response = client.post("/api/local-render/jobs", headers=_auth(), json=_local_job_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["render_target"] == "local"
    assert payload["job_dir"] == ""
    assert payload["status"] == "local_pending"
    assert payload["settings"]["render_profile"] == "auto"
    assert payload["videos"][0]["status"] == "local_pending"
    assert payload["videos"][0]["local_input_path"] == "/Users/test/clip.mp4"
    assert "<layout" in payload["videos"][0]["layout_xml"]


def test_create_local_render_job_requires_source_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    payload = _local_job_payload()
    assert isinstance(payload["videos"], list)
    payload["videos"][0]["source_resolution"] = None

    response = client.post("/api/local-render/jobs", headers=_auth(), json=payload)

    assert response.status_code == 400
    assert "source_resolution is required" in response.json()["detail"]


def test_media_library_local_render_requires_r2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)

    response = client.post("/api/local-render/jobs", headers=_auth(), json=_media_library_job_payload())

    assert response.status_code == 503


def test_worker_token_can_update_own_local_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    worker_token = _paired_worker_token(monkeypatch)
    create_response = client.post("/api/local-render/jobs", headers=_auth(), json=_local_job_payload())
    assert create_response.status_code == 200
    job_id = create_response.json()["id"]
    video_id = create_response.json()["videos"][0]["id"]

    update_response = client.patch(
        f"/api/local-render/jobs/{job_id}",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "status": "local_running",
            "progress": 42,
            "message": "Rendering locally",
            "videos": [
                {
                    "video_id": video_id,
                    "status": "local_running",
                    "progress": 42,
                    "detail": "Rendering with h264-source",
                }
            ],
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["status"] == "local_running"
    assert payload["progress"] == 42
    assert payload["worker_session_id"]
    assert payload["worker_version"] == "0.1.0"
    assert payload["videos"][0]["progress"] == 42


def test_worker_token_cannot_update_other_users_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    user_a_worker_token = _paired_worker_token(monkeypatch, uid="user-a")
    create_response = client.post("/api/local-render/jobs", headers=_auth("user-b"), json=_local_job_payload())
    assert create_response.status_code == 200
    job_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/local-render/jobs/{job_id}",
        headers={"Authorization": f"Bearer {user_a_worker_token}"},
        json={"status": "local_running", "progress": 25},
    )

    assert update_response.status_code == 404


def test_worker_can_create_upload_target_for_media_library_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "R2_UPLOAD_ENABLED", True)
    monkeypatch.setattr(api_main, "R2_BUCKET", "bucket-a")
    monkeypatch.setattr(api_main, "_signed_r2_upload_url", lambda object_key, content_type: f"https://upload.example/{object_key}")
    worker_token = _paired_worker_token(monkeypatch)
    create_response = client.post("/api/local-render/jobs", headers=_auth(), json=_media_library_job_payload())
    assert create_response.status_code == 200
    job_payload = create_response.json()
    job_id = job_payload["id"]
    video_id = job_payload["videos"][0]["id"]

    response = client.post(
        f"/api/local-render/jobs/{job_id}/upload-target",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={"video_id": video_id, "output_name": "clip-overlay.mp4", "content_type": "video/mp4"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "PUT"
    assert payload["bucket"] == "bucket-a"
    assert payload["object_key"].endswith("/clip-overlay.mp4")
    assert payload["upload_url"].startswith("https://upload.example/")


def test_worker_can_complete_media_library_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "R2_UPLOAD_ENABLED", True)
    monkeypatch.setattr(api_main, "R2_BUCKET", "bucket-a")
    monkeypatch.setattr(api_main, "_signed_r2_upload_url", lambda object_key, content_type: "https://upload.example/output")
    monkeypatch.setattr(
        api_main,
        "_verify_r2_object",
        lambda object_key: {
            "r2_object_key": object_key,
            "r2_bucket": "bucket-a",
            "r2_etag": "etag-a",
            "r2_uploaded_at": "2026-01-01T00:00:00+00:00",
            "output_size_bytes": 5,
        },
    )
    worker_token = _paired_worker_token(monkeypatch)
    create_response = client.post("/api/local-render/jobs", headers=_auth(), json=_media_library_job_payload())
    assert create_response.status_code == 200
    job_payload = create_response.json()
    job_id = job_payload["id"]
    video_id = job_payload["videos"][0]["id"]
    target_response = client.post(
        f"/api/local-render/jobs/{job_id}/upload-target",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={"video_id": video_id, "output_name": "clip-overlay.mp4", "content_type": "video/mp4"},
    )
    assert target_response.status_code == 200

    complete_response = client.post(
        f"/api/local-render/jobs/{job_id}/upload-complete",
        headers={"Authorization": f"Bearer {worker_token}"},
        json={
            "video_id": video_id,
            "output_name": "clip-overlay.mp4",
            "output_size_bytes": 5,
            "local_output_path": "/Users/test/POVerlay/clip-overlay.mp4",
        },
    )

    assert complete_response.status_code == 200
    video = complete_response.json()["videos"][0]
    assert video["status"] == "completed"
    assert video["r2_bucket"] == "bucket-a"
    assert video["r2_etag"] == "etag-a"
    assert video["local_output_path"] == "/Users/test/POVerlay/clip-overlay.mp4"
