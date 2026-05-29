from __future__ import annotations

from pathlib import Path

from poverlay_worker.profiles import RenderProfile
from poverlay_worker.render import RenderClip, RenderSettings, build_renderer_command, parse_progress_percent


def test_parse_progress_percent_accepts_renderer_format() -> None:
    assert parse_progress_percent("Render [ 42%] drawing frames") == 42
    assert parse_progress_percent("[100%] complete") == 100
    assert parse_progress_percent("no progress here") is None


def test_build_renderer_command_matches_server_render_contract() -> None:
    command = build_renderer_command(
        renderer_bin=Path("/opt/poverlay/gopro-dashboard.py"),
        gpx_path=Path("/tmp/track.gpx"),
        clip=RenderClip(
            input_path=Path("/tmp/input.mp4"),
            output_path=Path("/tmp/output.mp4"),
            layout_path=Path("/tmp/layout.xml"),
            overlay_size=(3840, 2160),
        ),
        settings=RenderSettings(
            font_path=Path("/tmp/font.ttf"),
            map_style="osm",
            speed_units="mph",
            altitude_units="feet",
            distance_units="mile",
            temperature_units="degF",
            fps_mode="fixed",
            fixed_fps=30,
        ),
        profile=RenderProfile(id="local-h264-software", label="H.264 Software", output_args=("-vcodec", "libx264")),
        config_dir=Path("/tmp/config"),
        cache_dir=Path("/tmp/cache"),
    )

    assert command[:2] == ["/opt/poverlay/gopro-dashboard.py", "--font"]
    assert "--use-gpx-only" in command
    assert "--video-time-start" in command
    assert "file-modified" in command
    assert "--layout-xml" in command
    assert "/tmp/layout.xml" in command
    assert "--profile" in command
    assert "local-h264-software" in command
    assert "--overlay-size" in command
    assert "3840x2160" in command
    assert "--overlay-fps" in command
    assert command[-2:] == ["/tmp/input.mp4", "/tmp/output.mp4"]


def test_build_renderer_command_accepts_renderer_args() -> None:
    command = build_renderer_command(
        renderer_bin=Path("/opt/poverlay/poverlay-worker"),
        renderer_args=["dashboard"],
        gpx_path=Path("/tmp/track.gpx"),
        clip=RenderClip(
            input_path=Path("/tmp/input.mp4"),
            output_path=Path("/tmp/output.mp4"),
            layout_path=Path("/tmp/layout.xml"),
        ),
        settings=RenderSettings(
            font_path=Path("/tmp/font.ttf"),
            map_style="osm",
            speed_units="mph",
            altitude_units="feet",
            distance_units="mile",
            temperature_units="degF",
        ),
        profile=RenderProfile(id="local-h264-software", label="H.264 Software", output_args=("-vcodec", "libx264")),
        config_dir=Path("/tmp/config"),
        cache_dir=Path("/tmp/cache"),
    )

    assert command[:2] == ["/opt/poverlay/poverlay-worker", "dashboard"]
