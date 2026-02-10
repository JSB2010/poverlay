from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

# Ensure the apps/api package root is importable when tests run from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402


client = TestClient(app)


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
