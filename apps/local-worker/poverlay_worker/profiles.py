from __future__ import annotations

from dataclasses import dataclass
import platform
import subprocess
from typing import Any


@dataclass(frozen=True)
class FfmpegCapabilities:
    encoders: frozenset[str]
    hwaccels: frozenset[str]


@dataclass(frozen=True)
class RenderProfile:
    id: str
    label: str
    output_args: tuple[str, ...]
    filter: str | None = None


def _parse_ffmpeg_names(output: str) -> frozenset[str]:
    names: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("-") or line.endswith(":"):
            continue
        parts = line.split()
        if not parts:
            continue
        if parts[0].startswith(("V", "A", "S")) and len(parts) > 1:
            names.add(parts[1])
            continue
        if len(parts) == 1 and parts[0].replace("_", "").replace("-", "").isalnum():
            names.add(parts[0])
    return frozenset(names)


def parse_capabilities(encoders_output: str, hwaccels_output: str) -> FfmpegCapabilities:
    return FfmpegCapabilities(
        encoders=_parse_ffmpeg_names(encoders_output),
        hwaccels=_parse_ffmpeg_names(hwaccels_output),
    )


def detect_capabilities(ffmpeg_bin: str = "ffmpeg") -> FfmpegCapabilities:
    encoders = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=False,
    )
    hwaccels = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-hwaccels"],
        capture_output=True,
        text=True,
        check=False,
    )
    return parse_capabilities(encoders.stdout, hwaccels.stdout)


def _h264_fallback() -> RenderProfile:
    return RenderProfile(
        id="local-h264-software",
        label="H.264 Software",
        output_args=(
            "-vcodec",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "19",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ),
    )


def _h264_4k_compat(capabilities: FfmpegCapabilities, *, system: str | None = None) -> RenderProfile:
    system_name = (system or platform.system()).lower()
    encoders = capabilities.encoders
    filter_graph = "[0:v]scale=min(3840\\,iw):-2:flags=lanczos[main];[main][1:v]overlay"

    if system_name != "darwin" and "h264_nvenc" in encoders:
        return RenderProfile(
            id="h264-4k-compat",
            label="H.264 4K Compatibility (NVIDIA NVENC)",
            output_args=(
                "-vcodec",
                "h264_nvenc",
                "-preset",
                "p5",
                "-b:v",
                "40M",
                "-maxrate",
                "50M",
                "-bufsize",
                "80M",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
            ),
            filter=filter_graph,
        )

    return RenderProfile(
        id="h264-4k-compat",
        label="H.264 4K Compatibility",
        output_args=(
            "-vcodec",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-maxrate",
            "40M",
            "-bufsize",
            "80M",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-level",
            "5.1",
            "-movflags",
            "+faststart",
        ),
        filter=filter_graph,
    )


def _h264_fast() -> RenderProfile:
    return RenderProfile(
        id="h264-fast",
        label="H.264 Fast Draft",
        output_args=("-vcodec", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart"),
    )


def _h264_source() -> RenderProfile:
    return RenderProfile(
        id="h264-source",
        label="H.264 Source Resolution",
        output_args=(
            "-vcodec",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "19",
            "-maxrate",
            "70M",
            "-bufsize",
            "140M",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-movflags",
            "+faststart",
        ),
    )


def _parse_resolution(value: str | None) -> tuple[int, int] | None:
    if not value or "x" not in value:
        return None
    width_raw, height_raw = value.lower().split("x", 1)
    try:
        width = int(width_raw.strip())
        height = int(height_raw.strip())
    except ValueError:
        return None
    if width < 2 or height < 2:
        return None
    return width, height


def choose_profile(
    capabilities: FfmpegCapabilities,
    *,
    system: str | None = None,
    prefer_hevc: bool = True,
    requested_profile: str | None = None,
    source_resolution: str | None = None,
) -> RenderProfile:
    system_name = (system or platform.system()).lower()
    encoders = capabilities.encoders
    resolution = _parse_resolution(source_resolution)
    high_resolution = bool(resolution and (resolution[0] > 3840 or resolution[1] > 2160))
    requested = str(requested_profile or "").strip()

    if requested == "h264-4k-compat" or (requested == "auto" and high_resolution):
        return _h264_4k_compat(capabilities, system=system)
    if requested == "h264-fast":
        return _h264_fast()
    if requested == "h264-source":
        return _h264_source()

    if system_name == "darwin" and prefer_hevc and "hevc_videotoolbox" in encoders:
        profile_id = requested if requested in {"qt-hevc-balanced", "qt-hevc-high"} else "local-hevc-videotoolbox"
        bitrate = "70M" if requested == "qt-hevc-high" else "45M"
        maxrate = "90M" if requested == "qt-hevc-high" else "60M"
        bufsize = "140M" if requested == "qt-hevc-high" else "90M"
        return RenderProfile(
            id=profile_id,
            label="HEVC VideoToolbox",
            output_args=(
                "-vcodec",
                "hevc_videotoolbox",
                "-tag:v",
                "hvc1",
                "-b:v",
                bitrate,
                "-maxrate",
                maxrate,
                "-bufsize",
                bufsize,
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
            ),
        )

    if "hevc_nvenc" in encoders and prefer_hevc:
        return RenderProfile(
            id="local-hevc-nvenc",
            label="HEVC NVIDIA NVENC",
            output_args=(
                "-vcodec",
                "hevc_nvenc",
                "-preset",
                "p5",
                "-b:v",
                "45M",
                "-maxrate",
                "60M",
                "-bufsize",
                "90M",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
            ),
        )

    if "h264_nvenc" in encoders:
        return RenderProfile(
            id="local-h264-nvenc",
            label="H.264 NVIDIA NVENC",
            output_args=(
                "-vcodec",
                "h264_nvenc",
                "-preset",
                "p5",
                "-b:v",
                "45M",
                "-maxrate",
                "60M",
                "-bufsize",
                "90M",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
            ),
        )

    if "hevc_qsv" in encoders and prefer_hevc:
        return RenderProfile(
            id="local-hevc-qsv",
            label="HEVC Intel Quick Sync",
            output_args=("-vcodec", "hevc_qsv", "-global_quality", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart"),
        )

    if "h264_qsv" in encoders:
        return RenderProfile(
            id="local-h264-qsv",
            label="H.264 Intel Quick Sync",
            output_args=("-vcodec", "h264_qsv", "-global_quality", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart"),
        )

    if "hevc_amf" in encoders and prefer_hevc:
        return RenderProfile(
            id="local-hevc-amf",
            label="HEVC AMD AMF",
            output_args=("-vcodec", "hevc_amf", "-quality", "quality", "-pix_fmt", "yuv420p", "-movflags", "+faststart"),
        )

    if "h264_amf" in encoders:
        return RenderProfile(
            id="local-h264-amf",
            label="H.264 AMD AMF",
            output_args=("-vcodec", "h264_amf", "-quality", "quality", "-pix_fmt", "yuv420p", "-movflags", "+faststart"),
        )

    return _h264_fallback()


def ffmpeg_profiles_json(profile: RenderProfile) -> dict[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "input": [],
        "output": list(profile.output_args),
    }
    if profile.filter:
        payload["filter"] = profile.filter
    return {profile.id: payload}
