from __future__ import annotations

from copy import deepcopy
import json
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


def test_invalid_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    response = client.get("/api/jobs/job-1", headers={"Authorization": "Bearer not-valid"})
    assert response.status_code == 401


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

    files = [
        ("gpx", ("track.gpx", b"<gpx></gpx>", "application/gpx+xml")),
        ("videos", ("clip.mp4", b"fake-video", "video/mp4")),
    ]
    response = client.post("/api/jobs", files=files, headers={"Authorization": "Bearer token-user-a"})
    assert response.status_code == 200

    job_id = response.json()["job_id"]
    assert fake_job_store[job_id]["uid"] == "user-a"


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
