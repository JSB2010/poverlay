from __future__ import annotations

from dataclasses import dataclass
import platform
import subprocess


@dataclass(frozen=True)
class FfmpegCapabilities:
    encoders: frozenset[str]
    hwaccels: frozenset[str]


@dataclass(frozen=True)
class RenderProfile:
    id: str
    label: str
    output_args: tuple[str, ...]


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


def choose_profile(
    capabilities: FfmpegCapabilities,
    *,
    system: str | None = None,
    prefer_hevc: bool = True,
) -> RenderProfile:
    system_name = (system or platform.system()).lower()
    encoders = capabilities.encoders

    if system_name == "darwin" and prefer_hevc and "hevc_videotoolbox" in encoders:
        return RenderProfile(
            id="local-hevc-videotoolbox",
            label="HEVC VideoToolbox",
            output_args=(
                "-vcodec",
                "hevc_videotoolbox",
                "-tag:v",
                "hvc1",
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


def ffmpeg_profiles_json(profile: RenderProfile) -> dict[str, dict[str, list[str]]]:
    return {
        profile.id: {
            "input": [],
            "output": list(profile.output_args),
        }
    }

