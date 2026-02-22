from __future__ import annotations

from pathlib import Path
import sys

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[3]
VENDOR_PATH = REPO_ROOT / "vendor" / "gopro-dashboard-overlay"
if str(VENDOR_PATH) not in sys.path:
    sys.path.insert(0, str(VENDOR_PATH))

from gopro_overlay.widgets.map import MaybeRoundedBorder, MovingMap  # noqa: E402


def test_moving_map_odd_size_bounds_keep_exact_square_crop() -> None:
    target_size = 419
    widget = MovingMap(
        at=None,
        location=lambda: None,
        azimuth=lambda: None,
        renderer=lambda m: Image.new("RGBA", m.size, (0, 0, 0, 0)),
        size=target_size,
        corner_radius=67,
    )

    left, top, right, bottom = widget.bounds
    assert right - left == target_size
    assert bottom - top == target_size


def test_rounded_border_mask_matches_actual_image_size() -> None:
    border = MaybeRoundedBorder(size=419, corner_radius=67, opacity=0.7)

    odd_crop = Image.new("RGBA", (419, 419), (0, 0, 0, 0))
    border.rounded(odd_crop)

    # Historically this raised ValueError("images do not match") when odd crop math
    # produced a one-pixel mismatch against the cached mask size.
    off_by_one_crop = Image.new("RGBA", (420, 420), (0, 0, 0, 0))
    border.rounded(off_by_one_crop)
