from __future__ import annotations

from pathlib import Path

from poverlay_worker import upload


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False


def test_upload_file_to_presigned_url_streams_with_content_length(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "output.mp4"
    path.write_bytes(b"video")
    captured = {}

    def fake_urlopen(req, timeout):  # noqa: ANN001
        captured["timeout"] = timeout
        captured["method"] = req.get_method()
        captured["content_length"] = req.get_header("Content-length")
        captured["content_type"] = req.get_header("Content-type")
        captured["data"] = req.data.read()
        return FakeResponse()

    monkeypatch.setattr(upload.request, "urlopen", fake_urlopen)

    upload.upload_file_to_presigned_url(
        path,
        {"upload_url": "https://upload.example/output", "method": "PUT", "headers": {"Content-Type": "video/mp4"}},
        timeout=12,
    )

    assert captured["timeout"] == 12
    assert captured["method"] == "PUT"
    assert captured["content_length"] == "5"
    assert captured["content_type"] == "video/mp4"
    assert captured["data"] == b"video"
