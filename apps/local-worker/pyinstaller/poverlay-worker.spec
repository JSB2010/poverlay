# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


spec_dir = Path(globals().get("SPECPATH", Path.cwd())).resolve()
if spec_dir.is_file():
    spec_dir = spec_dir.parent
local_worker_root = spec_dir.parent
repo_root = local_worker_root.parents[1]
sys.path.insert(0, str(local_worker_root))
dashboard_root = repo_root / "vendor" / "gopro-dashboard-overlay"
font_file = repo_root / "apps" / "api" / "app" / "static" / "fonts" / "Orbitron-Bold.ttf"
hiddenimports = [
    *collect_submodules("poverlay_worker"),
    *collect_submodules("gopro_overlay"),
]
datas = [
    *collect_data_files("gopro_overlay"),
    *collect_data_files("geotiler"),
    *[
        (str(path), str(Path("vendor") / "gopro-dashboard-overlay" / path.relative_to(dashboard_root).parent))
        for path in dashboard_root.rglob("*")
        if path.is_file()
    ],
    (str(font_file), "fonts"),
]

a = Analysis(
    [str(spec_dir / "launcher.py")],
    pathex=[str(local_worker_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="poverlay-worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
