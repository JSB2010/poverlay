from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from poverlay_worker import service
from poverlay_worker.service import app
from poverlay_worker.profiles import RenderProfile


client = TestClient(app)


def setup_function() -> None:
    with service.STATE_LOCK:
        service.STATE.api_base_url = None
        service.STATE.worker_token = None
        service.STATE.worker_session_id = None
        service.STATE.local_token = None
        service.STATE.uid = None
        service.STATE.current_job_id = None
        service.STATE.status = "idle"


def test_health_reports_unpaired_worker() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["paired"] is False


def test_pairing_complete_stores_worker_and_returns_local_token(monkeypatch) -> None:
    monkeypatch.setenv("POVERLAY_ALLOWED_API_BASES", "https://api.example.test")

    def fake_post_json(url, payload):  # noqa: ANN001
        assert url == "https://api.example.test/api/local-render/pairing/complete"
        assert payload["pairing_code"] == "pair-123"
        return {
            "worker_token": "worker-token",
            "worker_session_id": "session-1",
            "uid": "user-a",
        }

    monkeypatch.setattr(service, "post_json", fake_post_json)

    response = client.post(
        "/pairing/complete",
        json={"api_base_url": "https://api.example.test", "pairing_code": "pair-123"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["paired"] is True
    assert payload["local_token"]


def test_pairing_rejects_untrusted_api_host() -> None:
    response = client.post(
        "/pairing/complete",
        json={"api_base_url": "https://attacker.example", "pairing_code": "pair-123"},
    )

    assert response.status_code == 403


def test_pairing_rejects_untrusted_browser_origin(monkeypatch) -> None:
    monkeypatch.setenv("POVERLAY_ALLOWED_API_BASES", "https://api.example.test")

    response = client.post(
        "/pairing/complete",
        headers={"Origin": "https://attacker.example"},
        json={"api_base_url": "https://api.example.test", "pairing_code": "pair-123"},
    )

    assert response.status_code == 403


def test_pairing_allows_configured_browser_origin(monkeypatch) -> None:
    monkeypatch.setenv("POVERLAY_ALLOWED_API_BASES", "https://api.example.test")
    monkeypatch.setenv("POVERLAY_ALLOWED_WEB_ORIGINS", "https://studio.example.test")

    def fake_post_json(url, payload):  # noqa: ANN001
        return {
            "worker_token": "worker-token",
            "worker_session_id": "session-1",
            "uid": "user-a",
        }

    monkeypatch.setattr(service, "post_json", fake_post_json)

    response = client.post(
        "/pairing/complete",
        headers={"Origin": "https://studio.example.test"},
        json={"api_base_url": "https://api.example.test", "pairing_code": "pair-123"},
    )

    assert response.status_code == 200


def test_jobs_requires_local_token() -> None:
    response = client.post(
        "/jobs",
        data={"job_manifest": json.dumps({"id": "job-1"})},
        files=[
            ("gpx", ("track.gpx", b"<gpx />", "application/gpx+xml")),
            ("videos", ("clip.mp4", b"video", "video/mp4")),
        ],
    )

    assert response.status_code == 401


def test_jobs_saves_uploads_and_queues_background(monkeypatch, tmp_path: Path) -> None:
    with service.STATE_LOCK:
        service.STATE.api_base_url = "https://api.example.test"
        service.STATE.worker_token = "worker-token"
        service.STATE.local_token = "local-token"

    monkeypatch.setattr(service, "_job_root", lambda job_id: tmp_path / job_id)
    queued: list[tuple[str, dict[str, object], Path, dict[str, Path]]] = []

    def fake_run(job_id, manifest, gpx_path, video_paths):  # noqa: ANN001
        queued.append((job_id, manifest, gpx_path, video_paths))

    monkeypatch.setattr(service, "_run_local_job", fake_run)
    manifest = {
        "id": "job-1",
        "videos": [{"id": "video-1", "input_name": "clip.mp4", "layout_xml": "<layout />"}],
        "settings": {},
    }

    response = client.post(
        "/jobs",
        headers={"X-POVerlay-Local-Token": "local-token"},
        data={"job_manifest": json.dumps(manifest)},
        files=[
            ("gpx", ("track.gpx", b"<gpx />", "application/gpx+xml")),
            ("videos", ("clip.mp4", b"video", "video/mp4")),
        ],
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": True, "job_id": "job-1"}
    assert queued
    job_id, queued_manifest, gpx_path, video_paths = queued[0]
    assert job_id == "job-1"
    assert queued_manifest["id"] == "job-1"
    assert gpx_path.read_bytes() == b"<gpx />"
    assert video_paths["clip.mp4"].read_bytes() == b"video"


def test_jobs_endpoint_runs_local_only_render_and_reports_output(monkeypatch, tmp_path: Path) -> None:
    with service.STATE_LOCK:
        service.STATE.api_base_url = "https://api.example.test"
        service.STATE.worker_token = "worker-token"
        service.STATE.local_token = "local-token"

    monkeypatch.setattr(service, "_job_root", lambda job_id: tmp_path / job_id)
    monkeypatch.setattr(service, "detect_capabilities", lambda: object())
    monkeypatch.setattr(
        service,
        "choose_profile",
        lambda capabilities: RenderProfile(id="local-h264-software", label="H.264 Software", output_args=("-vcodec", "libx264")),
    )
    monkeypatch.setattr(service, "write_ffmpeg_profile", lambda config_dir, profile: config_dir / "ffmpeg-profiles.json")
    monkeypatch.setattr(service, "_bundled_font_path", lambda: tmp_path / "font.ttf")
    (tmp_path / "font.ttf").write_bytes(b"font")

    patched: list[tuple[str, dict[str, object]]] = []

    def fake_patch(job_id, payload):  # noqa: ANN001
        patched.append((job_id, payload))

    def fake_run_renderer(command):  # noqa: ANN001
        output_path = Path(command[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"rendered")
        yield {"progress": 25}
        yield {"progress": 100}
        yield {"return_code": 0}

    monkeypatch.setattr(service, "_patch_job", fake_patch)
    monkeypatch.setattr(service, "run_renderer_command", fake_run_renderer)

    manifest = {
        "id": "job-1",
        "upload_intent": "local_only",
        "font_path": "/server-only/font.ttf",
        "settings": {
            "map_style": "osm",
            "speed_units": "mph",
            "altitude_units": "feet",
            "distance_units": "mile",
            "temperature_units": "degF",
        },
        "videos": [{"id": "video-1", "input_name": "clip.mp4", "layout_xml": "<layout />"}],
    }

    response = client.post(
        "/jobs",
        headers={"X-POVerlay-Local-Token": "local-token"},
        data={"job_manifest": json.dumps(manifest)},
        files=[
            ("gpx", ("track.gpx", b"<gpx />", "application/gpx+xml")),
            ("videos", ("clip.mp4", b"video", "video/mp4")),
        ],
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": True, "job_id": "job-1"}
    assert patched[-1][1]["status"] == "completed"
    completed_video_updates = [
        video
        for _, payload in patched
        for video in payload.get("videos", [])
        if isinstance(video, dict) and video.get("status") == "completed"
    ]
    assert completed_video_updates
    assert completed_video_updates[-1]["output_name"] == "clip-overlay.mp4"
    assert Path(str(completed_video_updates[-1]["local_output_path"])).read_bytes() == b"rendered"


def test_default_worker_renderer_uses_python_module_in_dev(monkeypatch) -> None:
    monkeypatch.setattr(service.sys, "executable", "/usr/bin/python3")

    renderer_bin, renderer_args = service._default_worker_renderer()

    assert str(renderer_bin) == "/usr/bin/python3"
    assert renderer_args == ["-m", "poverlay_worker.main", "dashboard"]


def test_font_path_uses_existing_manifest_path(tmp_path: Path) -> None:
    font_path = tmp_path / "local.ttf"
    font_path.write_bytes(b"font")

    assert service._font_path_from_manifest({"font_path": str(font_path)}) == font_path


def test_font_path_falls_back_when_manifest_path_is_not_local(monkeypatch, tmp_path: Path) -> None:
    bundled_font = tmp_path / "Orbitron-Bold.ttf"
    bundled_font.write_bytes(b"font")
    monkeypatch.setattr(service, "_bundled_font_path", lambda: bundled_font)

    assert service._font_path_from_manifest({"font_path": "/server-only/font.ttf"}) == bundled_font


def test_run_local_job_uploads_media_library_output(monkeypatch, tmp_path: Path) -> None:
    with service.STATE_LOCK:
        service.STATE.api_base_url = "https://api.example.test"
        service.STATE.worker_token = "worker-token"

    monkeypatch.setattr(service, "_job_root", lambda job_id: tmp_path / job_id)
    monkeypatch.setattr(
        service,
        "detect_capabilities",
        lambda: object(),
    )
    monkeypatch.setattr(
        service,
        "choose_profile",
        lambda capabilities: RenderProfile(id="local-h264-software", label="H.264 Software", output_args=("-vcodec", "libx264")),
    )
    monkeypatch.setattr(service, "write_ffmpeg_profile", lambda config_dir, profile: config_dir / "ffmpeg-profiles.json")

    posted: list[tuple[str, dict[str, object]]] = []
    patched: list[tuple[str, dict[str, object]]] = []

    def fake_post(path, payload):  # noqa: ANN001
        posted.append((path, payload))
        if path.endswith("/upload-target"):
            return {"upload_url": "https://upload.example/output", "method": "PUT", "headers": {"Content-Type": "video/mp4"}}
        return {"ok": True}

    def fake_patch(job_id, payload):  # noqa: ANN001
        patched.append((job_id, payload))

    output_events = [{"progress": 50}, {"return_code": 0}]

    def fake_run_renderer(command):  # noqa: ANN001
        output_path = Path(command[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"video")
        yield from output_events

    monkeypatch.setattr(service, "_post_worker_api", fake_post)
    monkeypatch.setattr(service, "_patch_job", fake_patch)
    monkeypatch.setattr(service, "upload_file_to_presigned_url", lambda output_path, upload_target: posted.append(("uploaded", {"path": str(output_path)})))
    monkeypatch.setattr(service, "run_renderer_command", fake_run_renderer)

    manifest = {
        "id": "job-1",
        "upload_intent": "media_library",
        "renderer_bin": "/bin/echo",
        "font_path": "/tmp/font.ttf",
        "settings": {
            "map_style": "osm",
            "speed_units": "mph",
            "altitude_units": "feet",
            "distance_units": "mile",
            "temperature_units": "degF",
        },
        "videos": [{"id": "video-1", "input_name": "clip.mp4", "layout_xml": "<layout />"}],
    }
    input_path = tmp_path / "clip.mp4"
    input_path.write_bytes(b"input")
    gpx_path = tmp_path / "track.gpx"
    gpx_path.write_text("<gpx />", encoding="utf-8")

    service._run_local_job("job-1", manifest, gpx_path, {"clip.mp4": input_path})

    assert any(path.endswith("/upload-target") for path, _ in posted)
    assert any(path == "uploaded" for path, _ in posted)
    assert any(path.endswith("/upload-complete") for path, _ in posted)
    assert patched[-1][1]["status"] == "completed"
