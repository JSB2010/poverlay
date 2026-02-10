from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the apps/api package root is importable when tests run from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.layouts import DEFAULT_LAYOUT_STYLE, LAYOUT_STYLES, render_layout_xml  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)

NEW_LAYOUT_STYLE_IDS = (
    "moto-journey-needle",
    "moto-journey-dual-bars",
    "compass-asi-cluster",
    "power-zone-pro",
)


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
