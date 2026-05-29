from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from poverlay_worker import service as worker_service
from poverlay_worker.profiles import RenderProfile

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

import app.main as api_main  # noqa: E402
from app.main import app as api_app  # noqa: E402
from poverlay_worker.service import app as worker_app  # noqa: E402


api_client = TestClient(api_app)
worker_client = TestClient(worker_app)


@pytest.fixture(autouse=True)
def isolated_local_render_state(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, object]]:
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
    monkeypatch.setattr(api_main, "LOCAL_RENDER_ENABLED", True)
    monkeypatch.setattr(api_main, "R2_UPLOAD_ENABLED", False)
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)

    with api_main.JOBS_LOCK:
        api_main.JOBS.clear()
    with api_main.LOCAL_RENDER_LOCK:
        api_main.LOCAL_RENDER_PAIRINGS.clear()
        api_main.LOCAL_RENDER_WORKER_SESSIONS.clear()

    with worker_service.STATE_LOCK:
        worker_service.STATE.api_base_url = None
        worker_service.STATE.worker_token = None
        worker_service.STATE.worker_session_id = None
        worker_service.STATE.local_token = None
        worker_service.STATE.uid = None
        worker_service.STATE.current_job_id = None
        worker_service.STATE.status = "idle"

    yield store

    with api_main.JOBS_LOCK:
        api_main.JOBS.clear()
    with api_main.LOCAL_RENDER_LOCK:
        api_main.LOCAL_RENDER_PAIRINGS.clear()
        api_main.LOCAL_RENDER_WORKER_SESSIONS.clear()

    with worker_service.STATE_LOCK:
        worker_service.STATE.api_base_url = None
        worker_service.STATE.worker_token = None
        worker_service.STATE.worker_session_id = None
        worker_service.STATE.local_token = None
        worker_service.STATE.uid = None
        worker_service.STATE.current_job_id = None
        worker_service.STATE.status = "idle"


def _stub_verify_token(token: str) -> str:
    if token == "token-user-a":
        return "user-a"
    raise HTTPException(status_code=401, detail="Invalid or expired token")


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer token-user-a"}


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


def test_api_and_worker_complete_local_only_render_lifecycle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    api_base_url = "https://api.example.test"
    monkeypatch.setenv("POVERLAY_ALLOWED_API_BASES", api_base_url)

    def fake_post_json(url: str, payload: dict[str, object], bearer_token: str | None = None) -> dict[str, object]:  # noqa: ARG001
        parsed = urlparse(url)
        assert f"{parsed.scheme}://{parsed.netloc}" == api_base_url
        response = api_client.post(parsed.path, json=payload)
        assert response.status_code == 200, response.text
        return response.json()

    def fake_patch_json(url: str, payload: dict[str, object], bearer_token: str | None = None) -> dict[str, object]:
        parsed = urlparse(url)
        assert f"{parsed.scheme}://{parsed.netloc}" == api_base_url
        response = api_client.patch(
            parsed.path,
            headers={"Authorization": f"Bearer {bearer_token}"},
            json=payload,
        )
        assert response.status_code == 200, response.text
        return response.json()

    monkeypatch.setattr(worker_service, "post_json", fake_post_json)
    monkeypatch.setattr(worker_service, "patch_json", fake_patch_json)
    monkeypatch.setattr(worker_service, "_job_root", lambda job_id: tmp_path / job_id)
    monkeypatch.setattr(worker_service, "detect_capabilities", lambda: object())
    monkeypatch.setattr(
        worker_service,
        "choose_profile",
        lambda capabilities: RenderProfile(  # noqa: ARG005
            id="local-h264-software",
            label="H.264 Software",
            output_args=("-vcodec", "libx264"),
        ),
    )
    monkeypatch.setattr(worker_service, "write_ffmpeg_profile", lambda config_dir, profile: config_dir / "ffmpeg-profiles.json")
    font_path = tmp_path / "Orbitron-Bold.ttf"
    font_path.write_bytes(b"font")
    monkeypatch.setattr(worker_service, "_bundled_font_path", lambda: font_path)

    def fake_run_renderer(command: list[str]):
        output_path = Path(command[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"rendered")
        yield {"progress": 25}
        yield {"progress": 100}
        yield {"return_code": 0}

    monkeypatch.setattr(worker_service, "run_renderer_command", fake_run_renderer)

    start_response = api_client.post("/api/local-render/pairing/start", headers=_auth())
    assert start_response.status_code == 200

    pair_response = worker_client.post(
        "/pairing/complete",
        headers={"Origin": "http://localhost:3000"},
        json={"api_base_url": api_base_url, "pairing_code": start_response.json()["pairing_code"]},
    )
    assert pair_response.status_code == 200
    local_token = pair_response.json()["local_token"]
    assert pair_response.json()["paired"] is True

    create_response = api_client.post("/api/local-render/jobs", headers=_auth(), json=_local_job_payload())
    assert create_response.status_code == 200
    job_manifest = create_response.json()
    job_id = job_manifest["id"]
    video_id = job_manifest["videos"][0]["id"]
    assert job_manifest["videos"][0]["layout_xml"]

    worker_job_response = worker_client.post(
        "/jobs",
        headers={"X-POVerlay-Local-Token": local_token},
        data={"job_manifest": json.dumps(job_manifest)},
        files=[
            ("gpx", ("track.gpx", b"<gpx />", "application/gpx+xml")),
            ("videos", ("clip.mp4", b"video", "video/mp4")),
        ],
    )
    assert worker_job_response.status_code == 200
    assert worker_job_response.json() == {"accepted": True, "job_id": job_id}

    status_response = api_client.get(f"/api/jobs/{job_id}", headers=_auth())
    assert status_response.status_code == 200
    final_job = status_response.json()
    final_video = final_job["videos"][0]
    assert final_job["status"] == "completed"
    assert final_job["progress"] == 100
    assert final_job["worker_session_id"] == pair_response.json()["worker_session_id"]
    assert final_job["worker_version"] == "0.1.0"
    assert final_job["worker_platform"]
    assert final_video["id"] == video_id
    assert final_video["status"] == "completed"
    assert final_video["output_name"] == "clip-overlay.mp4"
    assert final_video["output_size_bytes"] == len(b"rendered")
    assert Path(final_video["local_output_path"]).read_bytes() == b"rendered"


def test_api_and_worker_complete_media_library_upload_lifecycle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    api_base_url = "https://api.example.test"
    monkeypatch.setenv("POVERLAY_ALLOWED_API_BASES", api_base_url)
    monkeypatch.setattr(api_main, "R2_UPLOAD_ENABLED", True)
    monkeypatch.setattr(api_main, "R2_BUCKET", "bucket-a")
    monkeypatch.setattr(api_main, "_signed_r2_upload_url", lambda object_key, content_type: f"https://upload.example/{object_key}")
    monkeypatch.setattr(
        api_main,
        "_verify_r2_object",
        lambda object_key: {
            "r2_object_key": object_key,
            "r2_bucket": "bucket-a",
            "r2_etag": "etag-a",
            "r2_uploaded_at": "2026-01-01T00:00:00+00:00",
            "output_size_bytes": len(b"rendered"),
        },
    )

    api_posts: list[tuple[str, dict[str, object]]] = []
    uploads: list[dict[str, object]] = []

    def fake_post_json(url: str, payload: dict[str, object], bearer_token: str | None = None) -> dict[str, object]:
        parsed = urlparse(url)
        assert f"{parsed.scheme}://{parsed.netloc}" == api_base_url
        api_posts.append((parsed.path, payload))
        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
        response = api_client.post(parsed.path, headers=headers, json=payload)
        assert response.status_code == 200, response.text
        return response.json()

    def fake_patch_json(url: str, payload: dict[str, object], bearer_token: str | None = None) -> dict[str, object]:
        parsed = urlparse(url)
        assert f"{parsed.scheme}://{parsed.netloc}" == api_base_url
        response = api_client.patch(
            parsed.path,
            headers={"Authorization": f"Bearer {bearer_token}"},
            json=payload,
        )
        assert response.status_code == 200, response.text
        return response.json()

    def fake_upload_file_to_presigned_url(output_path: Path, upload_target: dict[str, object]) -> None:
        uploads.append({"path": str(output_path), "target": upload_target})
        assert output_path.read_bytes() == b"rendered"
        assert str(upload_target["upload_url"]).startswith("https://upload.example/")

    monkeypatch.setattr(worker_service, "post_json", fake_post_json)
    monkeypatch.setattr(worker_service, "patch_json", fake_patch_json)
    monkeypatch.setattr(worker_service, "upload_file_to_presigned_url", fake_upload_file_to_presigned_url)
    monkeypatch.setattr(worker_service, "_job_root", lambda job_id: tmp_path / job_id)
    monkeypatch.setattr(worker_service, "detect_capabilities", lambda: object())
    monkeypatch.setattr(
        worker_service,
        "choose_profile",
        lambda capabilities: RenderProfile(  # noqa: ARG005
            id="local-h264-software",
            label="H.264 Software",
            output_args=("-vcodec", "libx264"),
        ),
    )
    monkeypatch.setattr(worker_service, "write_ffmpeg_profile", lambda config_dir, profile: config_dir / "ffmpeg-profiles.json")
    font_path = tmp_path / "Orbitron-Bold.ttf"
    font_path.write_bytes(b"font")
    monkeypatch.setattr(worker_service, "_bundled_font_path", lambda: font_path)

    def fake_run_renderer(command: list[str]):
        output_path = Path(command[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"rendered")
        yield {"progress": 100}
        yield {"return_code": 0}

    monkeypatch.setattr(worker_service, "run_renderer_command", fake_run_renderer)

    start_response = api_client.post("/api/local-render/pairing/start", headers=_auth())
    assert start_response.status_code == 200
    pair_response = worker_client.post(
        "/pairing/complete",
        headers={"Origin": "http://localhost:3000"},
        json={"api_base_url": api_base_url, "pairing_code": start_response.json()["pairing_code"]},
    )
    assert pair_response.status_code == 200
    local_token = pair_response.json()["local_token"]

    create_response = api_client.post("/api/local-render/jobs", headers=_auth(), json=_media_library_job_payload())
    assert create_response.status_code == 200
    job_manifest = create_response.json()
    job_id = job_manifest["id"]
    video_id = job_manifest["videos"][0]["id"]

    worker_job_response = worker_client.post(
        "/jobs",
        headers={"X-POVerlay-Local-Token": local_token},
        data={"job_manifest": json.dumps(job_manifest)},
        files=[
            ("gpx", ("track.gpx", b"<gpx />", "application/gpx+xml")),
            ("videos", ("clip.mp4", b"video", "video/mp4")),
        ],
    )
    assert worker_job_response.status_code == 200
    assert worker_job_response.json() == {"accepted": True, "job_id": job_id}

    assert uploads
    assert any(path.endswith("/upload-target") for path, _ in api_posts)
    assert any(path.endswith("/upload-complete") for path, _ in api_posts)

    status_response = api_client.get(f"/api/jobs/{job_id}", headers=_auth())
    assert status_response.status_code == 200
    final_job = status_response.json()
    final_video = final_job["videos"][0]
    assert final_job["status"] == "completed"
    assert final_video["id"] == video_id
    assert final_video["status"] == "completed"
    assert final_video["output_name"] == "clip-overlay.mp4"
    assert final_video["r2_bucket"] == "bucket-a"
    assert final_video["r2_etag"] == "etag-a"
    assert final_video["r2_object_key"].endswith("/clip-overlay.mp4")
    assert final_video["download_url"] == f"/api/jobs/{job_id}/download/clip-overlay.mp4"
    assert Path(final_video["local_output_path"]).read_bytes() == b"rendered"
