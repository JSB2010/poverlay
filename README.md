# POVerlay

POVerlay is a GoPro telemetry overlay platform that aligns one GPX track to one or more clips and renders polished overlays for each output video.

The app is now split into a modern monorepo architecture:

- `apps/web`: Next.js (App Router + TypeScript) frontend
- `apps/api`: FastAPI backend API and render orchestration
- `vendor/gopro-dashboard-overlay`: vendored rendering engine

## Why this architecture

- Ready for future auth and richer routed UI (Next.js)
- Clear API/frontend separation for VPS deployment
- Easy horizontal scaling path (web + API can be split later)
- Uses `pnpm` workspace for fast, deterministic JS dependency management

## Stack

- Frontend: Next.js 16 + React 19 + TypeScript
- Backend: FastAPI
- Renderer: `gopro-dashboard-overlay` + ffmpeg/ffprobe
- Process/deploy: systemd + Nginx (templates included)

## Local development

### Prerequisites

- Python 3.10+
- Node.js 20+
- ffmpeg / ffprobe
- pnpm (installed by `corepack` during setup when available)

### Setup

```bash
./scripts/setup.sh
```

### Run (web + API)

```bash
./scripts/run.sh
```

Services:

- Web UI: [http://localhost:3000](http://localhost:3000)
- API: [http://localhost:8787](http://localhost:8787)

### Quality checks

```bash
pnpm check
```

GitHub Actions CI runs the same command on push/PR via `.github/workflows/ci.yml`.

## API overview

- `GET /health` - health probe
- `GET /api/meta` - available themes/layouts/components/render profiles
- `POST /api/jobs` - create render job
- `GET /api/jobs/{job_id}` - poll job status
- `GET /api/jobs/{job_id}/download/{filename}` - output video
- `GET /api/jobs/{job_id}/log/{filename}` - renderer log
- `GET /api/jobs/{job_id}/download-all` - zip bundle for all outputs

## Environment variables

Backend:

- `GOPRO_DASHBOARD_BIN`
- `FFPROBE_BIN`
- `OVERLAY_FONT_PATH`
- `CORS_ORIGINS`
- `JOB_OUTPUT_RETENTION_HOURS`
- `JOB_CLEANUP_INTERVAL_SECONDS`
- `JOB_CLEANUP_ENABLED`
- `DELETE_INPUTS_ON_COMPLETE`
- `DELETE_WORK_ON_COMPLETE`

Frontend:

- `NEXT_PUBLIC_API_BASE` (optional; direct browser API base)
- `API_PROXY_TARGET` (used by Next rewrite for `/api/*`, default `http://127.0.0.1:8787`)

See `apps/web/.env.example`.

## VPS deployment

Deployment artifacts are included:

- systemd units: `deploy/systemd/poverlay-api.service`, `deploy/systemd/poverlay-web.service`
- Nginx site: `deploy/nginx/poverlay.conf`
- step-by-step guide: `deploy/VPS.md`
- deployment command: `./scripts/deploy-vps.sh --branch main --public-url https://poverlay.com`
- staging bootstrap command: `./scripts/bootstrap-staging-vps.sh`
- staging deploy workflow: `.github/workflows/deploy-staging.yml`
- production deploy workflow: `.github/workflows/deploy.yml`

## Repository layout

- `apps/web/app/*` - redesigned frontend experience
- `apps/api/app/main.py` - API, job lifecycle, rendering pipeline
- `apps/api/app/layouts.py` - overlay layout XML generation
- `apps/api/app/gpx_tools.py` - GPX timestamp/speed normalization helpers
- `apps/api/tests/*` - API baseline tests
- `scripts/setup.sh` - full Python + frontend bootstrapping
- `scripts/run.sh` - run web and API in parallel

## Notes

- Job artifacts are written to `data/jobs/<job-id>/`.
- Cleanup defaults are enabled for VPS-friendly disk usage.
- Vendored renderer source is tracked under `vendor/gopro-dashboard-overlay`.
