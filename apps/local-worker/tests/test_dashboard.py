from __future__ import annotations

from pathlib import Path

from poverlay_worker import dashboard


def test_dashboard_main_runs_configured_script(monkeypatch, tmp_path: Path) -> None:
    script = tmp_path / "gopro-dashboard.py"
    marker = tmp_path / "marker.txt"
    script.write_text(
        "import pathlib, sys\n"
        f"pathlib.Path({str(marker)!r}).write_text('|'.join(sys.argv[1:]), encoding='utf-8')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("POVERLAY_GOPRO_DASHBOARD_SCRIPT", str(script))

    assert dashboard.dashboard_main(["--version-probe"]) == 0
    assert marker.read_text(encoding="utf-8") == "--version-probe"

