# POVerlay VPS Deployment

This deployment model runs two services behind Nginx:

- `poverlay-api` (FastAPI) on `127.0.0.1:8787`
- `poverlay-web` (Next.js) on `127.0.0.1:3000`

## 1) Install system dependencies

```bash
sudo apt update
sudo apt install -y ffmpeg nginx python3 python3-venv python3-pip curl
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo corepack enable
sudo corepack prepare pnpm@9.15.4 --activate
```

## 2) Clone and build

```bash
sudo mkdir -p /opt/poverlay
sudo chown -R $USER:$USER /opt/poverlay
git clone <your-repo-url> /opt/poverlay
cd /opt/poverlay
./scripts/setup.sh
pnpm check
```

## 3) Runtime environment

Use the centralized root env template, then install it as the systemd env file:

```bash
cd /opt/poverlay
cp .env.example .env

# Edit `.env` with production values for Firebase/Firestore/R2/Brevo.
# Keep integration toggles false until credentials are ready.
#   FIREBASE_AUTH_ENABLED=true
#   FIRESTORE_ENABLED=true
#   R2_UPLOAD_ENABLED=true
#   BREVO_NOTIFICATIONS_ENABLED=true

sudo mkdir -p /etc/poverlay
cat .env | sudo tee /etc/poverlay/poverlay.env >/dev/null
```

Minimum baseline variables to set for VPS:

```bash
cat <<'ENV' | sudo tee -a /etc/poverlay/poverlay.env >/dev/null
WEB_BASE_URL=https://your-domain.com
API_BASE_URL=https://your-domain.com/api
NEXT_PUBLIC_SITE_URL=https://your-domain.com
API_PROXY_TARGET=http://127.0.0.1:8787
CORS_ORIGINS=https://your-domain.com,http://localhost:3000,http://127.0.0.1:3000
ADMIN_UIDS=your-firebase-uid
JOB_OUTPUT_RETENTION_HOURS=24
JOB_CLEANUP_INTERVAL_SECONDS=900
JOB_CLEANUP_ENABLED=true
JOB_RECOVERY_INTERVAL_SECONDS=45
JOB_QUEUE_WORKER_COUNT=0
FFMPEG_THREADS_PER_RENDER=0
JOB_DATABASE_CLEANUP_ENABLED=true
JOB_DATABASE_CLEANUP_INTERVAL_SECONDS=3600
JOB_DATABASE_RETENTION_DAYS=30
DELETE_INPUTS_ON_COMPLETE=true
DELETE_WORK_ON_COMPLETE=true
ENV
```

Integration-specific variables and secrets (required when integration toggle is `true`):

- Firebase auth (`FIREBASE_AUTH_ENABLED=true`, `NEXT_PUBLIC_FIREBASE_AUTH_ENABLED=true`)
- `FIREBASE_PROJECT_ID`
- One admin credential source: `FIREBASE_CREDENTIALS_JSON` or `FIREBASE_CREDENTIALS_PATH` (or `GOOGLE_APPLICATION_CREDENTIALS`) or `FIREBASE_ADMIN_CLIENT_EMAIL` + one `FIREBASE_ADMIN_PRIVATE_KEY*` value
- Web Firebase SDK config: `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID`, `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`, `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET`
- Firestore (`FIRESTORE_ENABLED=true`)
- `FIRESTORE_PROJECT_ID` (or rely on `FIREBASE_PROJECT_ID`), optional `FIRESTORE_DATABASE_ID`, optional collection overrides (`FIRESTORE_COLLECTION_*`)
- Cloudflare R2 (`R2_UPLOAD_ENABLED=true`)
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_ENDPOINT`, optional `R2_PUBLIC_BASE_URL`
- Brevo notifications (`BREVO_NOTIFICATIONS_ENABLED=true`)
- `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, optional `BREVO_SENDER_NAME`, optional `BREVO_TEMPLATE_RENDER_COMPLETE_ID`

Credential handling guidance:

- Keep secrets only in `/etc/poverlay/poverlay.env` (or a managed secret backend), not in git.
- Restrict env file permissions to root-readable only: `sudo chmod 600 /etc/poverlay/poverlay.env`.
- Use least-privilege service credentials (Firestore access only to required collections and R2 keys scoped to the target bucket).
- Restart both services after env changes: `sudo systemctl restart poverlay-api poverlay-web`.

## 4) Install systemd services

```bash
sudo cp deploy/systemd/poverlay-api.service /etc/systemd/system/
sudo cp deploy/systemd/poverlay-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now poverlay-api
sudo systemctl enable --now poverlay-web
```

## 5) Configure Nginx

```bash
sudo cp deploy/nginx/poverlay.conf /etc/nginx/sites-available/poverlay
sudo ln -sf /etc/nginx/sites-available/poverlay /etc/nginx/sites-enabled/poverlay
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

## 6) (Optional) HTTPS with Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Operational commands

```bash
sudo systemctl status poverlay-api poverlay-web
sudo journalctl -u poverlay-api -f
sudo journalctl -u poverlay-web -f
sudo systemctl restart poverlay-api poverlay-web
```

Auth/session behavior notes:

- Web sessions use Firebase local persistence and remain active across browser restarts until sign-out.
- API endpoints under `/api/jobs/*`, `/api/media*`, and `/api/user/settings` require `Authorization: Bearer <Firebase ID token>`.
- API token verification runs with revocation checks; revoked/expired tokens return `401`.

Restart and cleanup behavior:

- `poverlay-api` and `poverlay-web` systemd units use `Restart=always` with `RestartSec=3`.
- On API startup, queued/running jobs are recovered from Firestore and re-queued.
- A background reconciliation loop (`JOB_RECOVERY_INTERVAL_SECONDS`) continuously re-enqueues stranded queued/running jobs and prunes ghost queue state.
- If a recovered job references a missing local job directory, the job is marked `failed` with a restart-related message.
- Local render artifacts are deleted only after successful R2 upload verification for all produced outputs.
- Terminal jobs receive `expires_at`; background cleanup deletes expired `data/jobs/<job-id>` directories based on `JOB_OUTPUT_RETENTION_HOURS`.
- Cleanup cadence is controlled by `JOB_CLEANUP_ENABLED` and `JOB_CLEANUP_INTERVAL_SECONDS`.
- Optional Firestore metadata cleanup removes terminal job documents after `JOB_DATABASE_RETENTION_DAYS`.
- Admin endpoints under `/api/admin/*` require authenticated users whose UID is listed in `ADMIN_UIDS`.
- Web admins can monitor and trigger queue/cleanup actions at `/admin`.
- Admin queue controls include manual requeue and cancellation for queued/non-active jobs.

## Large upload testing (10GB+)

For large single-request uploads (for example 40GB), all layers must allow it:

1. Nginx:
   - `client_max_body_size 0;` (disables nginx body-size limit)
   - `proxy_request_buffering off;` in `location /api/`
   - long timeouts (`client_body_timeout`, `proxy_read_timeout`, `proxy_send_timeout`)
2. Web proxy (only if Next is proxying `/api`):
   - set `NEXT_PROXY_CLIENT_MAX_BODY_SIZE` high (for example `64gb`)
3. API host disk:
   - ensure enough free space in `/tmp` and app data paths for upload + processing.

Important: if DNS is proxied through Cloudflare ("orange cloud"), Cloudflare upload limits apply before your VPS.
See Cloudflare request-size limits: https://developers.cloudflare.com/workers/platform/limits/#request-limits
(plan-dependent and much lower than 40GB). For 40GB testing, use DNS-only/bypass Cloudflare or implement direct multipart uploads to object storage (recommended).

## Monitoring and smoke checks

Run after deploy or incident restart:

```bash
# Service health
curl -fsS http://127.0.0.1:8787/health
curl -fsS http://127.0.0.1:3000 >/dev/null

# Auth enforcement (expect 401 without token)
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/api/media
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/api/user/settings

# With Firebase ID token (expect 200)
curl -fsS -H "Authorization: Bearer ${ID_TOKEN}" http://127.0.0.1:8787/api/user/settings
curl -fsS -H "Authorization: Bearer ${ID_TOKEN}" "http://127.0.0.1:8787/api/media?page=1&page_size=1"
```

Use an ID token captured from an authenticated web session (browser devtools network request headers) or another trusted Firebase token issuance flow.

Log/alert checkpoints:

- `sudo journalctl -u poverlay-api -n 200 --no-pager | grep -E "Failed to persist job state|Render/upload failed|Job completion notification failed"`
- `sudo journalctl -u poverlay-api -n 200 --no-pager | grep -E "Resuming after API restart|missing on disk after restart"`
- `sudo systemctl is-active poverlay-api poverlay-web`

## Ongoing deploys (git-first workflow)

Run this on the VPS from `/opt/poverlay`:

```bash
./scripts/deploy-vps.sh --branch main --env-file /etc/poverlay/poverlay.env --public-url https://poverlay.com
```

Notes:

- This does a safe `git pull --ff-only` (no hard reset by default).
- By default it runs `pnpm check` (which includes build), then restarts services.
- The deploy script can auto-detect `/etc/poverlay/<service-prefix>.env`, but passing `--env-file` is recommended for clarity.
- Use `--skip-check` for faster deploys when needed.
- Use `--with-systemd` when you change `deploy/systemd/*`.
- Use `--with-nginx` only when you intentionally want to sync `deploy/nginx/poverlay.conf`.
- If your VPS nginx file is Certbot-managed, `--with-nginx` will refuse to overwrite it unless templates match Certbot layout.

## GitHub Actions auto-deploy

Workflows:

- `.github/workflows/deploy-staging.yml`: auto-deploys staging after CI passes on pushes to `main` (or manual dispatch).
- `.github/workflows/deploy.yml`: manual production deploy.

Set these repository secrets:

- `VPS_HOST` (example: `15.204.223.62`)
- `VPS_USER` (example: `ubuntu`)
- `VPS_SSH_KEY` (private key contents)
- `VPS_PORT` (optional, defaults to `22`)

Optional repository variables:

- `VPS_APP_DIR` (defaults to `/opt/poverlay`)
- `VPS_PUBLIC_URL` (defaults to `https://poverlay.com`)
- `VPS_STAGING_APP_DIR` (defaults to `/opt/poverlay-staging`)
- `VPS_STAGING_PUBLIC_URL` (defaults to `https://dev.poverlay.com`)

The workflow assumes the remote user can run `sudo -n` non-interactively.

## Staging on the same VPS

The repository includes staging service/nginx templates:

- `deploy/systemd/poverlay-staging-api.service`
- `deploy/systemd/poverlay-staging-web.service`
- `deploy/nginx/poverlay-dev.conf`

Recommended staging layout on the same host:

- app dir: `/opt/poverlay-staging`
- api port: `8788`
- web port: `3001`
- env file: `/etc/poverlay/poverlay-staging.env`
- domain: `dev.poverlay.com`

One-time bootstrap on VPS:

```bash
cd /opt/poverlay
./scripts/bootstrap-staging-vps.sh
```
