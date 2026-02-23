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

- App URLs/runtime: `WEB_BASE_URL`, `API_BASE_URL`, `NEXT_PUBLIC_SITE_URL`, CORS + admin/queue/cleanup controls (`ADMIN_UIDS`, `JOB_QUEUE_WORKER_COUNT`, `JOB_RECOVERY_INTERVAL_SECONDS`, `FFMPEG_THREADS_PER_RENDER`, `JOB_DATABASE_*`)
- Firebase: client SDK keys + admin credentials (`FIREBASE_*`, `NEXT_PUBLIC_FIREBASE_*`)
- Firestore: project/database/collection names (`FIRESTORE_*`)
- Cloudflare R2: account/bucket/credentials (`R2_*`)
- Brevo: notifications + sender/template settings (`BREVO_*`)

Production integration checklist (set in `/etc/poverlay/poverlay.env` on VPS):

- Keep auth toggles aligned: `FIREBASE_AUTH_ENABLED=true` and `NEXT_PUBLIC_FIREBASE_AUTH_ENABLED=true`.
- Durable pipeline toggles: `FIRESTORE_ENABLED=true` and `R2_UPLOAD_ENABLED=true`.
- Notification toggle: `BREVO_NOTIFICATIONS_ENABLED=true`.
- Firebase admin credentials: provide one source (`FIREBASE_CREDENTIALS_JSON`, `FIREBASE_CREDENTIALS_PATH`, or `FIREBASE_ADMIN_CLIENT_EMAIL` + one `FIREBASE_ADMIN_PRIVATE_KEY*` value).
- Firestore identity: set `FIRESTORE_PROJECT_ID` (or rely on `FIREBASE_PROJECT_ID`) and keep collection names consistent unless intentionally migrated.
- R2 credentials: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_ENDPOINT`.
- Brevo sender settings: `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, optional `BREVO_TEMPLATE_RENDER_COMPLETE_ID`.

Config validation is fail-fast:

- API startup validates enabled integrations in `apps/api/app/config.py`
- Web startup validates public Firebase env in `apps/web/lib/public-config.ts`

Use `./scripts/run.sh`, `./scripts/run-web.sh`, or `./scripts/run-api.sh` so root `.env` is loaded automatically.

## Auth and reliability notes

- Web auth persistence uses Firebase `browserLocalPersistence`, so sessions survive page reloads and browser restarts until explicit sign-out.
- API auth expects `Authorization: Bearer <Firebase ID token>` and verifies tokens with revocation checks.
- Job state is persisted in Firestore and the API recovers `queued`/`running` jobs at startup and on a periodic reconciliation loop.
- Queue workers are configurable via `JOB_QUEUE_WORKER_COUNT` (`0` = auto-size by CPU); ffmpeg thread budget per render is controlled with `FFMPEG_THREADS_PER_RENDER`.
- Completed outputs are uploaded to R2 before local artifacts are deleted; job metadata records `local_artifacts_deleted_at` after cleanup.
- Background cleanup removes expired job directories using `JOB_OUTPUT_RETENTION_HOURS` and `JOB_CLEANUP_INTERVAL_SECONDS`.
- Optional Firestore retention cleanup removes old terminal job metadata using `JOB_DATABASE_CLEANUP_ENABLED`, `JOB_DATABASE_CLEANUP_INTERVAL_SECONDS`, and `JOB_DATABASE_RETENTION_DAYS`.
- Admin operations endpoints (`/api/admin/*`) require Firebase auth plus `ADMIN_UIDS` allow-list membership.
- The web admin operations dashboard is available at `/admin` for authenticated allow-listed admins.
- Admin queue controls now include manual reconcile/cleanup, job requeue, and queued-job cancellation.

## Operator smoke checks

Run after deploy/restart:

```bash
curl -fsS http://127.0.0.1:8787/health
curl -fsS http://127.0.0.1:3000 >/dev/null
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/api/media
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/api/user/settings
```

Expected:

- Health endpoints return `200`.
- Unauthenticated `/api/media` and `/api/user/settings` return `401`.

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
