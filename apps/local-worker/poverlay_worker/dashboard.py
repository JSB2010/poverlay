from __future__ import annotations

from pathlib import Path
import os
import runpy
import sys


def _candidate_dashboard_scripts() -> list[Path]:
    here = Path(__file__).resolve()
    repo_root = here.parents[3] if len(here.parents) > 3 else here.parent
    candidates: list[Path] = []

    env_script = os.getenv("POVERLAY_GOPRO_DASHBOARD_SCRIPT")
    if env_script:
        candidates.append(Path(env_script).expanduser())

    candidates.extend(
        [
            repo_root / "vendor" / "gopro-dashboard-overlay" / "bin" / "gopro-dashboard.py",
            Path(getattr(sys, "_MEIPASS", "")) / "vendor" / "gopro-dashboard-overlay" / "bin" / "gopro-dashboard.py"
            if getattr(sys, "_MEIPASS", None)
            else Path(),
            Path(getattr(sys, "_MEIPASS", "")) / "gopro-dashboard.py" if getattr(sys, "_MEIPASS", None) else Path(),
            Path(sys.executable).with_name("gopro-dashboard.py"),
        ]
    )
    return [candidate for candidate in candidates if str(candidate)]


def dashboard_main(argv: list[str] | None = None) -> int:
    original_argv = sys.argv[:]
    args = list(argv or [])
    for script in _candidate_dashboard_scripts():
        if script.is_file():
            package_root = script.parent.parent
            if (package_root / "gopro_overlay").is_dir() and str(package_root) not in sys.path:
                sys.path.insert(0, str(package_root))
            sys.argv = [str(script), *args]
            try:
                runpy.run_path(str(script), run_name="__main__")
                return 0
            except SystemExit as exc:
                return int(exc.code or 0) if isinstance(exc.code, int) else 1
            finally:
                sys.argv = original_argv
    raise FileNotFoundError("Could not locate bundled gopro-dashboard.py renderer script")
