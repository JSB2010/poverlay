from __future__ import annotations

from poverlay_worker.profiles import FfmpegCapabilities, choose_profile, parse_capabilities


def test_parse_capabilities_reads_encoder_and_hwaccel_names() -> None:
    encoders = """
 Encoders:
 V..... libx264              libx264 H.264 / AVC
 V..... hevc_videotoolbox    VideoToolbox H.265 Encoder
 V..... h264_nvenc           NVIDIA NVENC H.264 encoder
"""
    hwaccels = """
 Hardware acceleration methods:
 videotoolbox
 cuda
"""

    capabilities = parse_capabilities(encoders, hwaccels)

    assert "libx264" in capabilities.encoders
    assert "hevc_videotoolbox" in capabilities.encoders
    assert "h264_nvenc" in capabilities.encoders
    assert "videotoolbox" in capabilities.hwaccels
    assert "cuda" in capabilities.hwaccels


def test_choose_profile_prefers_macos_videotoolbox_hevc() -> None:
    profile = choose_profile(
        FfmpegCapabilities(encoders=frozenset({"libx264", "hevc_videotoolbox"}), hwaccels=frozenset()),
        system="Darwin",
    )

    assert profile.id == "local-hevc-videotoolbox"
    assert "hevc_videotoolbox" in profile.output_args


def test_choose_profile_prefers_nvenc_before_software() -> None:
    profile = choose_profile(
        FfmpegCapabilities(encoders=frozenset({"libx264", "h264_nvenc"}), hwaccels=frozenset()),
        system="Windows",
    )

    assert profile.id == "local-h264-nvenc"
    assert "h264_nvenc" in profile.output_args


def test_choose_profile_keeps_software_fallback() -> None:
    profile = choose_profile(FfmpegCapabilities(encoders=frozenset({"libx264"}), hwaccels=frozenset()), system="Linux")

    assert profile.id == "local-h264-software"
    assert "libx264" in profile.output_args

