from __future__ import annotations

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
def clear_jobs_state() -> None:
    with api_main.JOBS_LOCK:
        api_main.JOBS.clear()
    yield
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


def test_invalid_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    response = client.get("/api/jobs/job-1", headers={"Authorization": "Bearer not-valid"})
    assert response.status_code == 401


def test_cross_user_job_access_returns_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    job_dir = tmp_path / "job-1"
    job_dir.mkdir(parents=True, exist_ok=True)

    with api_main.JOBS_LOCK:
        api_main.JOBS["job-1"] = {
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


def test_create_job_persists_authenticated_uid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(api_main, "_verify_firebase_token", _stub_verify_token)
    monkeypatch.setattr(api_main, "_ensure_ffmpeg_profiles", lambda: None)
    monkeypatch.setattr(api_main, "GOPRO_DASHBOARD_BIN", str(Path(__file__).resolve()))
    monkeypatch.setattr(api_main, "DEFAULT_FONT_PATH", str(Path(__file__).resolve()))
    monkeypatch.setattr(api_main, "JOBS_DIR", tmp_path / "jobs")

    async def _noop_save_upload(upload, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"test")
        await upload.close()

    class _NoopThread:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def start(self) -> None:
            return None

    monkeypatch.setattr(api_main, "_save_upload", _noop_save_upload)
    monkeypatch.setattr(api_main.threading, "Thread", _NoopThread)

    files = [
        ("gpx", ("track.gpx", b"<gpx></gpx>", "application/gpx+xml")),
        ("videos", ("clip.mp4", b"fake-video", "video/mp4")),
    ]
    response = client.post("/api/jobs", files=files, headers={"Authorization": "Bearer token-user-a"})
    assert response.status_code == 200

    job_id = response.json()["job_id"]
    with api_main.JOBS_LOCK:
        assert api_main.JOBS[job_id]["uid"] == "user-a"


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
