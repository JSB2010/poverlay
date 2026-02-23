#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def _run(cmd: list[str], *, check: bool = True, capture_output: bool = False, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture_output, text=text)


def _ffprobe_value(path: Path, key: str) -> str:
    return subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            f"stream={key}",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        text=True,
    ).strip()


def _write_fallback_gpx(path: Path, *, start_time: datetime, points: int) -> None:
    rows: list[str] = []
    lat = 37.4219999
    lon = -122.0840575
    ele = 12.0
    for index in range(points):
        current = start_time + timedelta(seconds=index)
        lat_point = lat + (index * 0.0001)
        lon_point = lon + (index * 0.0001)
        ele_point = ele + (index * 0.05)
        rows.append(
            "      "
            f'<trkpt lat="{lat_point:.7f}" lon="{lon_point:.7f}"><ele>{ele_point:.2f}</ele><time>{current.strftime("%Y-%m-%dT%H:%M:%SZ")}</time></trkpt>'
        )

    content = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="POVerlay Staging Benchmark" xmlns="http://www.topografix.com/GPX/1/1">',
            "  <trk>",
            "    <name>Benchmark Track</name>",
            "    <trkseg>",
            *rows,
            "    </trkseg>",
            "  </trk>",
            "</gpx>",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")


def _build_fallback_video(path: Path, *, width: int, height: int, fps: int, duration_seconds: float) -> None:
    _run(
        [
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
            f"{duration_seconds:.3f}",
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
        ],
        capture_output=True,
    )


def _main() -> int:
    parser = argparse.ArgumentParser(description="Run staging render benchmarks and emit CSV/JSON results.")
    parser.add_argument("--repo-root", default="/opt/poverlay-staging", help="Path to deployed repo on target host.")
    parser.add_argument("--duration", type=float, default=8.0, help="Clip duration (seconds) for benchmark samples.")
    parser.add_argument("--output-dir", required=True, help="Directory to write benchmark artifacts to.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    duration_seconds = max(1.0, float(args.duration))

    samples_video = repo_root / "samples" / "GX010288.MP4"
    samples_gpx = repo_root / "samples" / "February 7, 2026 - Breckenridge Resort.gpx"
    font_path = repo_root / "apps/api/app/static/fonts/Orbitron-Bold.ttf"
    config_dir = repo_root / "data/gopro-config"
    runner = repo_root / "scripts/gopro-dashboard-local.sh"

    if not runner.exists():
        raise RuntimeError(f"Missing renderer launcher: {runner}")

    output_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = output_dir / "clips"
    layouts_dir = output_dir / "layouts"
    renders_dir = output_dir / "outputs"
    logs_dir = output_dir / "logs"
    for path in [clips_dir, layouts_dir, renders_dir, logs_dir]:
        path.mkdir(parents=True, exist_ok=True)

    resolutions = [
        ("720p", 1280, 720),
        ("1080p", 1920, 1080),
        ("2_7k", 2704, 1520),
        ("4k", 3840, 2160),
        ("5_3k", 5312, 2988),
    ]
    profiles = ["h264-fast", "h264-source", "h264-4k-compat"]

    if not samples_video.exists() or not samples_gpx.exists():
        synthetic_dir = output_dir / "synthetic-samples"
        synthetic_dir.mkdir(parents=True, exist_ok=True)
        fallback_start = datetime(2026, 2, 7, 22, 28, 39, tzinfo=timezone.utc)
        fallback_video = synthetic_dir / "fallback-5_3k.mp4"
        fallback_gpx = synthetic_dir / "fallback-track.gpx"
        _build_fallback_video(
            fallback_video,
            width=5312,
            height=2988,
            fps=30,
            duration_seconds=max(duration_seconds + 5.0, 30.0),
        )
        _write_fallback_gpx(
            fallback_gpx,
            start_time=fallback_start,
            points=max(int(duration_seconds) + 120, 300),
        )
        timestamp = fallback_start.timestamp()
        os.utime(fallback_video, (timestamp, timestamp))
        samples_video = fallback_video
        samples_gpx = fallback_gpx

    creation_time = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format_tags=creation_time",
            "-of",
            "default=nw=1:nk=1",
            str(samples_video),
        ],
        text=True,
    ).strip()
    if not creation_time:
        # Fallback video may not carry creation_time metadata.
        creation_time = "2026-02-07T22:28:39Z"
    creation_ts = creation_time.replace("Z", "+00:00") if creation_time.endswith("Z") else creation_time

    print(f"[bench] source creation_time={creation_time}")
    print(f"[bench] clip duration={duration_seconds:.2f}s")

    for resolution_id, width, height in resolutions:
        clip_path = clips_dir / f"{resolution_id}.mp4"
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-ss",
                "00:00:30",
                "-t",
                f"{duration_seconds:.3f}",
                "-i",
                str(samples_video),
                "-vf",
                f"scale={width}:{height}:flags=lanczos",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                str(clip_path),
            ],
            capture_output=True,
        )
        _run(
            [
                "python3",
                "-c",
                (
                    "from datetime import datetime;"
                    "import os,sys;"
                    "dt=datetime.fromisoformat(sys.argv[2].replace('Z','+00:00'));"
                    "os.utime(sys.argv[1], (dt.timestamp(), dt.timestamp()))"
                ),
                str(clip_path),
                creation_ts,
            ]
        )

    sys.path.insert(0, str((repo_root / "apps/api").resolve()))
    from app.layouts import render_layout_xml  # noqa: PLC0415

    for resolution_id, width, height in resolutions:
        for maps_enabled in [False, True]:
            layout_path = layouts_dir / f"{resolution_id}-maps-{'on' if maps_enabled else 'off'}.xml"
            layout_path.write_text(
                render_layout_xml(
                    width=width,
                    height=height,
                    theme_name="powder-neon",
                    include_maps=maps_enabled,
                    layout_style="summit-grid",
                    speed_units="mph",
                ),
                encoding="utf-8",
            )

    timer_re = re.compile(r"Timer\(drawing frames - Called: (\d+), Total: ([0-9.]+), Avg: ([0-9.]+), Rate: ([0-9.]+)\)")

    def run_case(
        *,
        scenario: str,
        resolution_id: str,
        profile: str,
        maps_enabled: bool,
        fps_mode: str,
        fixed_fps: float | None,
    ) -> dict[str, object]:
        clip_path = clips_dir / f"{resolution_id}.mp4"
        output_path = renders_dir / f"{scenario}.mp4"
        log_path = logs_dir / f"{scenario}.log"
        layout_path = layouts_dir / f"{resolution_id}-maps-{'on' if maps_enabled else 'off'}.xml"

        cmd = [
            str(runner),
            "--font",
            str(font_path),
            "--gpx",
            str(samples_gpx),
            "--use-gpx-only",
            "--video-time-start",
            "file-modified",
            "--layout",
            "xml",
            "--layout-xml",
            str(layout_path),
            "--map-style",
            "osm",
            "--units-speed",
            "mph",
            "--units-altitude",
            "feet",
            "--units-distance",
            "mile",
            "--units-temperature",
            "degF",
            "--config-dir",
            str(config_dir),
            "--cache-dir",
            str(config_dir),
            "--profile",
            profile,
        ]

        if fps_mode == "source_rounded":
            cmd.append("--overlay-fps-round")
        elif fps_mode == "fixed":
            cmd.extend(["--overlay-fps", str(fixed_fps if fixed_fps is not None else 30.0)])

        cmd.extend(["--", str(clip_path), str(output_path)])

        started = time.perf_counter()
        completed = _run(cmd, check=False, capture_output=True)
        elapsed = time.perf_counter() - started

        combined = f"{completed.stdout}\n{completed.stderr}".strip()
        log_path.write_text(combined, encoding="utf-8")
        lines = [line.strip() for line in combined.splitlines() if line.strip()]
        error_excerpt = ""
        if completed.returncode != 0 and lines:
            for line in reversed(lines):
                lowered = line.lower()
                if any(token in lowered for token in ["traceback", "error", "exception", "failed", "fatal", "unable", "missing"]):
                    error_excerpt = line
                    break
            if not error_excerpt:
                error_excerpt = lines[-1]

        timer_match = timer_re.search(combined)
        draw_frames = int(timer_match.group(1)) if timer_match else None
        draw_total_s = float(timer_match.group(2)) if timer_match else None
        draw_rate_fps = float(timer_match.group(4)) if timer_match else None

        output_width = ""
        output_height = ""
        output_fps = ""
        output_duration = ""
        if completed.returncode == 0 and output_path.exists():
            output_width = _ffprobe_value(output_path, "width")
            output_height = _ffprobe_value(output_path, "height")
            output_fps = _ffprobe_value(output_path, "avg_frame_rate")
            output_duration = _ffprobe_value(output_path, "duration")

        wall_x_realtime = elapsed / duration_seconds
        print(
            f"[bench] {scenario} ret={completed.returncode} elapsed={elapsed:.2f}s x_rt={wall_x_realtime:.2f}x"
            + (f" err={error_excerpt}" if error_excerpt else "")
        )

        return {
            "scenario": scenario,
            "resolution_id": resolution_id,
            "profile": profile,
            "maps_enabled": maps_enabled,
            "fps_mode": fps_mode,
            "fixed_fps": fixed_fps if fixed_fps is not None else "",
            "clip_duration_s": round(duration_seconds, 3),
            "elapsed_s": round(elapsed, 3),
            "wall_x_realtime": round(wall_x_realtime, 3),
            "draw_frames": draw_frames if draw_frames is not None else "",
            "draw_total_s": round(draw_total_s, 3) if draw_total_s is not None else "",
            "draw_rate_fps": round(draw_rate_fps, 3) if draw_rate_fps is not None else "",
            "return_code": completed.returncode,
            "output_width": output_width,
            "output_height": output_height,
            "output_fps": output_fps,
            "output_duration": output_duration,
            "error_excerpt": error_excerpt,
            "log_path": str(log_path),
        }

    cases: list[dict[str, object]] = []

    for resolution_id, _w, _h in resolutions:
        for profile in profiles:
            cases.append(
                {
                    "scenario": f"main-{resolution_id}-{profile}",
                    "resolution_id": resolution_id,
                    "profile": profile,
                    "maps_enabled": False,
                    "fps_mode": "source_exact",
                    "fixed_fps": None,
                }
            )

    for resolution_id, _w, _h in resolutions:
        cases.append(
            {
                "scenario": f"maps-on-{resolution_id}-h264-source",
                "resolution_id": resolution_id,
                "profile": "h264-source",
                "maps_enabled": True,
                "fps_mode": "source_exact",
                "fixed_fps": None,
            }
        )

    for resolution_id in ["1080p", "5_3k"]:
        for fps_mode, fixed in [("source_rounded", None), ("fixed", 15.0), ("fixed", 30.0)]:
            cases.append(
                {
                    "scenario": f"fps-{resolution_id}-h264-source-{fps_mode}-{fixed if fixed else 'na'}",
                    "resolution_id": resolution_id,
                    "profile": "h264-source",
                    "maps_enabled": False,
                    "fps_mode": fps_mode,
                    "fixed_fps": fixed,
                }
            )

    rows = [run_case(**case) for case in cases]

    csv_path = output_dir / "results.csv"
    json_path = output_dir / "results.json"
    summary_path = output_dir / "summary.json"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    main_rows = [row for row in rows if str(row["scenario"]).startswith("main-") and int(row["return_code"]) == 0]
    summary: dict[str, dict[str, object]] = {}
    for row in main_rows:
        key = f"{row['resolution_id']}|{row['profile']}"
        summary[key] = {
            "resolution_id": row["resolution_id"],
            "profile": row["profile"],
            "wall_x_realtime": row["wall_x_realtime"],
            "elapsed_s": row["elapsed_s"],
            "clip_duration_s": row["clip_duration_s"],
            "output": f"{row['output_width']}x{row['output_height']}",
        }

    payload = {
        "duration_seconds": round(duration_seconds, 3),
        "total_cases": len(rows),
        "failed_cases": [row["scenario"] for row in rows if int(row["return_code"]) != 0],
        "main_matrix": summary,
        "artifacts": {
            "results_csv": str(csv_path),
            "results_json": str(json_path),
        },
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("[bench] summary:")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
