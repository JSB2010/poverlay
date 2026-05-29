from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable

from .profiles import RenderProfile, ffmpeg_profiles_json


PROGRESS_RE = re.compile(r"\[(\s*\d+)%\]")


@dataclass(frozen=True)
class RenderSettings:
    font_path: Path
    map_style: str
    speed_units: str
    altitude_units: str
    distance_units: str
    temperature_units: str
    fps_mode: str = "source_exact"
    fixed_fps: float = 30.0


@dataclass(frozen=True)
class RenderClip:
    input_path: Path
    output_path: Path
    layout_path: Path
    overlay_size: tuple[int, int] | None = None


def parse_progress_percent(line: str) -> int | None:
    match = PROGRESS_RE.search(line)
    if not match:
        return None
    return max(0, min(100, int(match.group(1).strip())))


def write_ffmpeg_profile(config_dir: Path, profile: RenderProfile) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    target = config_dir / "ffmpeg-profiles.json"
    target.write_text(json.dumps(ffmpeg_profiles_json(profile), indent=2), encoding="utf-8")
    return target


def build_renderer_command(
    *,
    renderer_bin: Path,
    renderer_args: list[str] | None = None,
    gpx_path: Path,
    clip: RenderClip,
    settings: RenderSettings,
    profile: RenderProfile,
    config_dir: Path,
    cache_dir: Path,
) -> list[str]:
    cmd = [
        str(renderer_bin),
        *(renderer_args or []),
        "--font",
        str(settings.font_path),
        "--gpx",
        str(gpx_path),
        "--use-gpx-only",
        "--video-time-start",
        "file-modified",
        "--layout",
        "xml",
        "--layout-xml",
        str(clip.layout_path),
        "--map-style",
        settings.map_style,
        "--units-speed",
        settings.speed_units,
        "--units-altitude",
        settings.altitude_units,
        "--units-distance",
        settings.distance_units,
        "--units-temperature",
        settings.temperature_units,
        "--config-dir",
        str(config_dir),
        "--cache-dir",
        str(cache_dir),
        "--profile",
        profile.id,
    ]

    if clip.overlay_size is not None:
        cmd.extend(["--overlay-size", f"{clip.overlay_size[0]}x{clip.overlay_size[1]}"])

    if settings.fps_mode == "source_rounded":
        cmd.append("--overlay-fps-round")
    elif settings.fps_mode == "fixed":
        cmd.extend(["--overlay-fps", str(settings.fixed_fps)])

    cmd.extend(["--", str(clip.input_path), str(clip.output_path)])
    return cmd


def run_renderer_command(command: list[str]) -> Iterable[dict[str, Any]]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        progress = parse_progress_percent(line)
        event: dict[str, Any] = {"line": line.rstrip("\n")}
        if progress is not None:
            event["progress"] = progress
        yield event

    return_code = process.wait()
    yield {"return_code": return_code}
