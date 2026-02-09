# GoPro GPX Overlay Studio

A local web app that renders polished telemetry overlays onto one or more GoPro clips from a single Slopes GPX track.

## What this solves

- Upload one `.gpx` file from Slopes
- Upload one or multiple GoPro videos from the same day
- Render one overlay output per video with:
  - speed
  - clock/time
  - altitude
  - grade/slope
  - distance
  - moving map + journey map (optional)
- Download each output video or a single `.zip`
- Automatically detect and match each clip's source FPS (24/25/30/50/60/etc.) with optional rounded/fixed override

## Base engine and research choice

This project uses `gopro-dashboard-overlay` as the render engine and wraps it in a clean FastAPI + web UI workflow.

Cloned source for adaptation/reference:
- `vendor/gopro-dashboard-overlay`

Why this was chosen:
- Active maintenance and recent updates
- Native support for GPX-driven overlays
- Highly configurable XML layout system
- Strong GoPro-focused rendering pipeline with ffmpeg integration

## Tech stack

- Backend: FastAPI
- Renderer: `gopro-overlay` (`gopro-dashboard.py`)
- Frontend: vanilla HTML/CSS/JS
- Video tooling: ffmpeg + ffprobe

## Quick start

```bash
./scripts/setup.sh
./scripts/run.sh
```

Open:

- [http://localhost:8787](http://localhost:8787)

## Synchronization model

The app renders in GPX-only mode and aligns each video using file timestamps.

- It reads `creation_time` from each video via `ffprobe`
- Sets file modified-time to that value
- Uses `--video-time-start file-modified` to sync GPX to video
- Optional `GPX time offset (seconds)` lets you shift the GPX clock to fine-tune sync
- GPX speed normalization converts Slopes-exported speed values to m/s for accurate overlay speeds (`Auto-detect` by default; manual override available in Advanced settings).
- Export profiles file (`data/gopro-config/ffmpeg-profiles.json`) is generated automatically by the app at runtime from backend profile definitions.

## Framerate behavior

- Default mode: `Match source (exact)`  
  - Each uploaded clip is probed and rendered at that clip's native FPS (for example `30000/1001`, `24`, `60`).
- Optional mode: `Match source (rounded int)`  
  - Useful if you want `29.97` to render as `30`.
- Optional mode: `Fixed FPS`  
  - Forces all outputs in the job to a single FPS value.

## Export codec behavior

- Default export profile is now `Auto (Recommended)`.
- `Auto` picks per clip:
  - macOS + >4K clips: `HEVC (QuickTime Balanced)` first, with compatibility fallbacks if needed.
  - lower-res clips: `H.264 (Source Resolution)` first.
  - non-macOS high-res clips: `H.264 (4K Compatibility)` first.
- Profiles in the UI:
  - `Auto (Recommended)`: chooses profile per clip for quality + smooth playback + compatibility.
  - `HEVC (QuickTime Balanced) - Recommended`: best default for high-res playback on Apple devices/software.
  - `HEVC (QuickTime High Quality)`: larger files, highest detail for Apple-oriented workflows.
  - `H.264 (Source Resolution)`: broad compatibility while preserving native resolution.
  - `H.264 (4K Compatibility)`: downscales >4K to 4K for smoother playback on mixed/older devices.
  - `H.264 (Fast Draft)`: fastest encode for quick previews.

## Themes and UI

- Theme colors are custom presets defined in `app/layouts.py`.
- Added additional built-in themes beyond the original two:
  - Powder Neon
  - Summit Ember
  - Glacier Steel
  - Forest Sprint
  - Night Sprint
  - Sunset Drive
- UI now separates quick settings from advanced settings, including:
  - units presets (Imperial/Metric/Custom)
  - per-metric unit overrides
  - GPX speed source unit override (Auto/mph/kph/mps/knots)

## Resolution and format support

- The renderer supports mixed uploads with different frame sizes and frame rates in the same job.
- Output FPS can match each source clip exactly (`29.97`, `59.94`, `24`, etc.) or use rounded/fixed modes.
- Source resolution is preserved by default unless you choose `H.264 (4K Compatibility)` (which intentionally caps >4K to 4K for playback compatibility).
- Practical constraints:
  - Clips should have valid creation timestamps for automatic GPX alignment; if not, use `GPX time offset`.
  - Extremely high-res/high-bitrate combinations can still stutter on weaker decoders even when encoded correctly.
  - Very unusual codecs/containers may decode but can be slower; MP4/H.264/H.265 remain the most reliable path.

## Main files

- `app/main.py`: API + job orchestration + rendering pipeline
- `app/layouts.py`: custom ski overlay layout generator (resolution-aware)
- `app/gpx_tools.py`: GPX timestamp shifting
- `app/static/index.html`: UI
- `app/static/styles.css`: visual design
- `app/static/app.js`: upload and live status polling

## Notes

- First render can take time for high-res clips (5.3K is heavy).
- If you disable maps, rendering is generally faster.
- Job artifacts are written under `data/jobs/<job-id>/`.

## VPS storage cleanup

The app can automatically clean job files to keep disk usage under control:

- deletes `inputs/` and `work/` after a job finishes
- keeps rendered outputs for a retention window
- periodically purges expired job directories
- `download-all` zip files are now temporary and auto-deleted after the response

Environment variables:

- `JOB_OUTPUT_RETENTION_HOURS` (default: `24`)
- `JOB_CLEANUP_INTERVAL_SECONDS` (default: `900`)
- `JOB_CLEANUP_ENABLED` (default: `true`)
- `DELETE_INPUTS_ON_COMPLETE` (default: `true`)
- `DELETE_WORK_ON_COMPLETE` (default: `true`)

Example for a small VPS:

```bash
export JOB_OUTPUT_RETENTION_HOURS=12
export JOB_CLEANUP_INTERVAL_SECONDS=600
export DELETE_INPUTS_ON_COMPLETE=true
export DELETE_WORK_ON_COMPLETE=true
```

## First Commit Checklist

- Do not commit local render outputs (`data/` is ignored).
- Do not commit large raw sample videos (`samples/*.MP4` and `samples/*.MOV` are ignored).
- Keep vendored renderer source, but remove any nested `.git` folder under `vendor/gopro-dashboard-overlay` before committing.
- Run a quick sanity check before commit:
  - `./scripts/setup.sh`
  - `python -m py_compile app/main.py app/gpx_tools.py app/layouts.py`
  - `node --check app/static/app.js` (if Node is installed)
  - `./scripts/run.sh`

## Initial Setup (New Machine)

```bash
git clone <your-repo-url>
cd gopro-speed
./scripts/setup.sh
./scripts/run.sh
```

Open [http://localhost:8787](http://localhost:8787).
