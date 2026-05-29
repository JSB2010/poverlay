from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .dashboard import dashboard_main
from .profiles import choose_profile, detect_capabilities
from .render import RenderClip, RenderSettings, build_renderer_command, run_renderer_command, write_ffmpeg_profile
from .service import DEFAULT_PORT, run_service


def _load_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Manifest must be a JSON object")
    return payload


def _render_from_manifest(path: Path) -> int:
    manifest = _load_manifest(path)
    profile = choose_profile(detect_capabilities(str(manifest.get("ffmpeg_bin") or "ffmpeg")))
    work_dir = Path(str(manifest["work_dir"]))
    config_dir = work_dir / "config"
    cache_dir = work_dir / "cache"
    write_ffmpeg_profile(config_dir, profile)

    settings_payload = manifest.get("settings")
    if not isinstance(settings_payload, dict):
        raise ValueError("Manifest settings must be an object")

    settings = RenderSettings(
        font_path=Path(str(settings_payload["font_path"])),
        map_style=str(settings_payload["map_style"]),
        speed_units=str(settings_payload["speed_units"]),
        altitude_units=str(settings_payload["altitude_units"]),
        distance_units=str(settings_payload["distance_units"]),
        temperature_units=str(settings_payload["temperature_units"]),
        fps_mode=str(settings_payload.get("fps_mode", "source_exact")),
        fixed_fps=float(settings_payload.get("fixed_fps", 30.0)),
    )

    clips_payload = manifest.get("clips")
    if not isinstance(clips_payload, list) or not clips_payload:
        raise ValueError("Manifest clips must be a non-empty array")

    renderer_bin = Path(str(manifest["renderer_bin"]))
    renderer_args = manifest.get("renderer_args")
    if renderer_args is not None and not isinstance(renderer_args, list):
        raise ValueError("renderer_args must be an array when provided")
    gpx_path = Path(str(manifest["gpx_path"]))
    exit_code = 0
    for raw_clip in clips_payload:
        if not isinstance(raw_clip, dict):
            raise ValueError("Each clip must be an object")
        overlay_size = raw_clip.get("overlay_size")
        clip = RenderClip(
            input_path=Path(str(raw_clip["input_path"])),
            output_path=Path(str(raw_clip["output_path"])),
            layout_path=Path(str(raw_clip["layout_path"])),
            overlay_size=tuple(overlay_size) if isinstance(overlay_size, list) and len(overlay_size) == 2 else None,
        )
        command = build_renderer_command(
            renderer_bin=renderer_bin,
            renderer_args=[str(arg) for arg in renderer_args] if renderer_args else None,
            gpx_path=gpx_path,
            clip=clip,
            settings=settings,
            profile=profile,
            config_dir=config_dir,
            cache_dir=cache_dir,
        )
        for event in run_renderer_command(command):
            print(json.dumps(event), flush=True)
            if event.get("return_code"):
                exit_code = int(event["return_code"])
    return exit_code


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if raw_argv and raw_argv[0] == "dashboard":
        return dashboard_main(raw_argv[1:])

    parser = argparse.ArgumentParser(description="POVerlay local render worker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("manifest", type=Path)
    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    subparsers.add_parser("dashboard")
    args = parser.parse_args(raw_argv)

    if args.command == "render":
        return _render_from_manifest(args.manifest)
    if args.command == "serve":
        run_service(host=args.host, port=args.port)
        return 0
    if args.command == "dashboard":
        return dashboard_main([])
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
