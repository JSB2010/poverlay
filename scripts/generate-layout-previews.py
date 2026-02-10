#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
WEB_PUBLIC_ROOT = REPO_ROOT / "apps" / "web" / "public"
DEFAULT_OUTPUT_DIR = WEB_PUBLIC_ROOT / "layout-previews"
DEFAULT_MANIFEST_PATH = DEFAULT_OUTPUT_DIR / "manifest.json"
DEFAULT_SAMPLES_DIR = REPO_ROOT / "samples"
DEFAULT_FONT_PATH = REPO_ROOT / "apps" / "api" / "app" / "static" / "fonts" / "Orbitron-Bold.ttf"
DEFAULT_CONFIG_DIR = REPO_ROOT / "data" / "gopro-config"
DEFAULT_THEME = "powder-neon"
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 30
DEFAULT_DURATION_SECONDS = 8
DEFAULT_CAPTURE_SECOND = 2.0
DEFAULT_PREVIEW_WIDTH = 640
DEFAULT_PREVIEW_HEIGHT = 360
DEFAULT_MAP_STYLE = "osm"
DEFAULT_RENDER_PROFILE = ""

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv"}
GPX_EXTENSIONS = {".gpx"}


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(cmd, check=False, text=True, env=env)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(cmd)}")


def _find_first_file(root: Path, extensions: set[str]) -> Path | None:
    if not root.exists():
        return None
    matches = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in extensions)
    return matches[0] if matches else None


def _write_fallback_gpx(path: Path, start_time: datetime, points: int, interval_seconds: int) -> None:
    rows: list[str] = []
    lat = 37.4219999
    lon = -122.0840575
    ele = 12.0
    for index in range(points):
        current = start_time + timedelta(seconds=index * interval_seconds)
        lat_point = lat + (index * 0.00015)
        lon_point = lon + (index * 0.00015)
        ele_point = ele + (index * 0.08)
        rows.append(
            "      "
            f'<trkpt lat="{lat_point:.7f}" lon="{lon_point:.7f}"><ele>{ele_point:.2f}</ele><time>{current.strftime("%Y-%m-%dT%H:%M:%SZ")}</time></trkpt>'
        )

    content = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="POVerlay Preview Generator" xmlns="http://www.topografix.com/GPX/1/1">',
            "  <trk>",
            "    <name>Deterministic Preview Track</name>",
            "    <trkseg>",
            *rows,
            "    </trkseg>",
            "  </trk>",
            "</gpx>",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")


def _build_fallback_video(path: Path, width: int, height: int, fps: int, duration_seconds: int) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={width}x{height}:rate={fps}",
        "-t",
        str(duration_seconds),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(path),
    ]
    _run(cmd)


def _extract_preview_frame(video_path: Path, output_path: Path, second: float, width: int, height: int) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{second:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={width}:{height}:flags=lanczos",
        "-compression_level",
        "9",
        str(output_path),
    ]
    _run(cmd)


def _load_layout_renderer():
    sys.path.insert(0, str(API_ROOT))
    from app.layouts import LAYOUT_STYLES, render_layout_xml  # noqa: PLC0415

    return LAYOUT_STYLES, render_layout_xml


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate deterministic layout preview screenshots from real overlay renders. "
            "Creates one PNG per layout style ID plus a mapping manifest."
        )
    )
    parser.add_argument("--gpx", type=Path, help="Optional GPX input path.")
    parser.add_argument("--video", type=Path, help="Optional video input path.")
    parser.add_argument("--samples-dir", type=Path, default=DEFAULT_SAMPLES_DIR, help="Directory to scan for sample GPX/video.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for preview PNG files.")
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Output manifest JSON path.",
    )
    parser.add_argument("--theme", default=DEFAULT_THEME, help="Overlay theme ID used for previews.")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Render width for intermediate overlay video.")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="Render height for intermediate overlay video.")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS, help="Fallback video FPS.")
    parser.add_argument("--duration-seconds", type=int, default=DEFAULT_DURATION_SECONDS, help="Fallback video duration.")
    parser.add_argument("--capture-second", type=float, default=DEFAULT_CAPTURE_SECOND, help="Timestamp used when extracting preview PNG.")
    parser.add_argument("--preview-width", type=int, default=DEFAULT_PREVIEW_WIDTH, help="Width of committed PNG preview.")
    parser.add_argument("--preview-height", type=int, default=DEFAULT_PREVIEW_HEIGHT, help="Height of committed PNG preview.")
    parser.add_argument("--map-style", default=DEFAULT_MAP_STYLE, help="Map style passed to renderer.")
    parser.add_argument(
        "--render-profile",
        default=DEFAULT_RENDER_PROFILE,
        help="Optional renderer profile name. Leave unset to use gopro-dashboard default.",
    )
    parser.add_argument("--include-maps", action="store_true", help="Include map widgets in rendered previews.")
    return parser.parse_args()


def _resolve_inputs(args: argparse.Namespace, tmp_dir: Path) -> tuple[Path, Path, str]:
    if bool(args.gpx) != bool(args.video):
        raise ValueError("Provide both --gpx and --video together, or neither.")

    if args.gpx and args.video:
        gpx_path = args.gpx.expanduser().resolve()
        video_path = args.video.expanduser().resolve()
        if not gpx_path.exists():
            raise FileNotFoundError(f"GPX file not found: {gpx_path}")
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        return gpx_path, video_path, "cli"

    sample_gpx = _find_first_file(args.samples_dir, GPX_EXTENSIONS)
    sample_video = _find_first_file(args.samples_dir, VIDEO_EXTENSIONS)
    if sample_gpx and sample_video:
        return sample_gpx, sample_video, "samples"

    fallback_start = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    gpx_path = tmp_dir / "fallback-track.gpx"
    video_path = tmp_dir / "fallback-video.mp4"
    points = max(args.duration_seconds + 10, 20)

    _write_fallback_gpx(gpx_path, fallback_start, points=points, interval_seconds=1)
    _build_fallback_video(video_path, args.width, args.height, args.fps, args.duration_seconds)

    timestamp = fallback_start.timestamp()
    os.utime(video_path, (timestamp, timestamp))

    return gpx_path, video_path, "deterministic-fallback"


def _ensure_runtime_prerequisites() -> None:
    python_path = REPO_ROOT / ".venv" / "bin" / "python"
    renderer = REPO_ROOT / "scripts" / "gopro-dashboard-local.sh"
    if not python_path.exists():
        raise RuntimeError(
            f"Missing renderer Python environment at {python_path}. "
            "Run `python3 -m venv .venv && .venv/bin/pip install -r apps/api/requirements-dev.txt`."
        )
    if not renderer.exists():
        raise RuntimeError(f"Missing renderer launcher: {renderer}")
    if not DEFAULT_FONT_PATH.exists():
        raise RuntimeError(f"Missing font file: {DEFAULT_FONT_PATH}")


def main() -> int:
    args = _parse_args()
    _ensure_runtime_prerequisites()

    if args.capture_second < 0:
        raise ValueError("--capture-second must be >= 0")

    LAYOUT_STYLES, render_layout_xml = _load_layout_renderer()
    layout_ids = list(LAYOUT_STYLES.keys())

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    for existing in args.output_dir.glob("*.png"):
        if existing.stem not in layout_ids:
            existing.unlink()

    with tempfile.TemporaryDirectory(prefix="layout-preview-gen-") as tmp:
        tmp_dir = Path(tmp)
        gpx_path, video_path, source_type = _resolve_inputs(args, tmp_dir)

        for style_id in layout_ids:
            layout_xml = render_layout_xml(
                args.width,
                args.height,
                args.theme,
                include_maps=bool(args.include_maps),
                layout_style=style_id,
                component_visibility=None,
                speed_units="kph",
            )
            layout_path = tmp_dir / f"{style_id}.xml"
            rendered_video_path = tmp_dir / f"{style_id}.mp4"
            preview_path = args.output_dir / f"{style_id}.png"

            layout_path.write_text(layout_xml, encoding="utf-8")

            render_cmd = [
                str(REPO_ROOT / "scripts" / "gopro-dashboard-local.sh"),
                "--font",
                str(DEFAULT_FONT_PATH),
                "--gpx",
                str(gpx_path),
                "--use-gpx-only",
                "--video-time-start",
                "file-modified",
                "--layout",
                "xml",
                "--layout-xml",
                str(layout_path),
                "--map-style",
                args.map_style,
                "--units-speed",
                "kph",
                "--units-altitude",
                "metre",
                "--units-distance",
                "km",
                "--units-temperature",
                "degC",
                "--config-dir",
                str(DEFAULT_CONFIG_DIR),
                "--",
                str(video_path),
                str(rendered_video_path),
            ]
            if args.render_profile:
                input_separator_index = render_cmd.index("--")
                render_cmd[input_separator_index:input_separator_index] = ["--profile", args.render_profile]
            _run(render_cmd, env={**os.environ, "PYTHONUNBUFFERED": "1"})
            _extract_preview_frame(
                rendered_video_path,
                preview_path,
                second=args.capture_second,
                width=args.preview_width,
                height=args.preview_height,
            )

    manifest = {
        "base_path": "/layout-previews",
        "format": "png",
        "preview_size": {"width": args.preview_width, "height": args.preview_height},
        "render_input_size": {"width": args.width, "height": args.height},
        "theme": args.theme,
        "input_source": source_type,
        "layout_ids": layout_ids,
        "images": {style_id: f"/layout-previews/{style_id}.png" for style_id in layout_ids},
    }
    args.manifest_path.write_text(f"{json.dumps(manifest, indent=2)}\n", encoding="utf-8")

    print(f"Generated {len(layout_ids)} layout previews in {args.output_dir}")
    print(f"Wrote manifest: {args.manifest_path}")
    print(f"Input source: {manifest['input_source']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
