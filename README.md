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

### Regenerate layout preview screenshots

```bash
scripts/generate-layout-previews.py
```

Notes:
- The script prefers sample inputs from `samples/` when both a `.gpx` and video file are present.
- If sample inputs are not present, it generates deterministic fallback GPX/video input and still produces one preview PNG per layout style ID.
- Output assets are written to `apps/web/public/layout-previews/` with a stable `manifest.json` mapping layout IDs to image paths.

## API overview

- `GET /health` - health probe
- `GET /api/meta` - available themes/layouts/components/render profiles
- `POST /api/jobs` - create render job
- `GET /api/jobs/{job_id}` - poll job status
- `GET /api/jobs/{job_id}/download/{filename}` - output video
- `GET /api/jobs/{job_id}/log/{filename}` - renderer log
- `GET /api/jobs/{job_id}/download-all` - zip bundle for all outputs

## Environment variables

Use one centralized env file at repo root:

```bash
cp .env.example .env
```

The root template includes:

- App URLs/runtime: `WEB_BASE_URL`, `API_BASE_URL`, `NEXT_PUBLIC_SITE_URL`, CORS + job cleanup settings
- Firebase: client SDK keys + admin credentials (`FIREBASE_*`, `NEXT_PUBLIC_FIREBASE_*`)
- Firestore: project/database/collection names (`FIRESTORE_*`)
- Cloudflare R2: account/bucket/credentials (`R2_*`)
- Brevo: notifications + sender/template settings (`BREVO_*`)

Config validation is fail-fast:

- API startup validates enabled integrations in `apps/api/app/config.py`
- Web startup validates public Firebase env in `apps/web/lib/public-config.ts`

Use `./scripts/run.sh`, `./scripts/run-web.sh`, or `./scripts/run-api.sh` so root `.env` is loaded automatically.

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
