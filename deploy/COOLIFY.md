# Coolify Deployment

This repository now deploys through Coolify using Docker Compose. The Compose file and Dockerfiles live in the repo so Coolify can build images directly from GitHub.

## Files

- `docker-compose.coolify.yml` - Coolify Compose stack (single source of truth)
- `deploy/docker/api.Dockerfile` - FastAPI container
- `deploy/docker/web.Dockerfile` - Next.js standalone container
- `.env.example` - environment variable template

## Coolify setup (recommended)

1. **Create a GitHub App source**
   - In Coolify: **Sources** → **Add** → GitHub App.
   - Complete the automated installation flow and grant access to this repo.

2. **Create a new resource**
   - Project → **Create New Resource**.
   - Choose **Private Repository (GitHub App)**.
   - Select this repository.

3. **Select build pack**
   - Choose **Docker Compose**.
   - **Base Directory:** `/` (repo root).
   - **Docker Compose Location:** `docker-compose.coolify.yml`.

4. **Environment variables**
   - Start with `.env.example`.
   - Required values:
     - `WEB_BASE_URL` (e.g., `https://poverlay.com`)
     - `API_BASE_URL` (e.g., `https://poverlay.com/api`)
     - `NEXT_PUBLIC_SITE_URL` (e.g., `https://poverlay.com`)
     - `NEXT_PUBLIC_API_BASE` (leave empty for the same-domain Next.js `/api` proxy, or use the site origin such as `https://poverlay.com`; do not append `/api`)
     - `CORS_ORIGINS` (include your public domain)
   - Recommended values:
     - `API_PROXY_TARGET=http://api:8787`
     - `NEXT_PROXY_CLIENT_MAX_BODY_SIZE=64gb`
     - `NEXT_PROXY_TIMEOUT_MS=1800000` for 30-minute proxied upload requests
   - Set **Build + Runtime** for `NEXT_PUBLIC_*`, `API_PROXY_TARGET`, `NEXT_PROXY_CLIENT_MAX_BODY_SIZE`, and `NEXT_PROXY_TIMEOUT_MS`.
   - Set **Runtime only** for secrets (Firebase admin keys, R2 keys, Brevo, etc).
   - If `FIRESTORE_ENABLED=true`, provide one Firebase service-account source to the API container: `FIREBASE_CREDENTIALS_JSON`, `FIREBASE_CREDENTIALS_PATH`, `GOOGLE_APPLICATION_CREDENTIALS`, or `FIREBASE_ADMIN_CLIENT_EMAIL` plus one `FIREBASE_ADMIN_PRIVATE_KEY*` value.

5. **Domains**
   - Assign your public domain to the **web** service and set the port to **3000**.
   - Keep the **api** service private (no domain).
   - For uploads larger than your public proxy can accept, assign a separate hostname to the **api** service on port **8787** and set `NEXT_PUBLIC_API_BASE` to that origin. If the hostname is behind Cloudflare and video uploads exceed Cloudflare's proxied upload cap, set that DNS record to **DNS-only**.

## Large upload failures

If `POST /api/jobs` fails after roughly 30 seconds with a browser `502` and no API-container log entry, the request is likely timing out in the Next.js rewrite proxy before FastAPI receives the full multipart body. Confirm by checking the **web** service logs for `Failed to proxy ... /api/jobs`.

Set `NEXT_PROXY_TIMEOUT_MS` to a value longer than the expected upload duration and redeploy the web image. The default in this repo is `1800000` ms (30 minutes). For very large files, prefer a direct API/upload hostname so the browser posts straight to FastAPI instead of tunneling through the web service.

If it fails after roughly 60 seconds and neither the web nor API service receives a useful app-level error, increase the Coolify proxy timeout. For the default Traefik proxy, add longer responding timeouts under **Servers > your server > Proxy > Configuration > Command**:

```yaml
--entrypoints.http.transport.respondingTimeouts.readTimeout=30m
--entrypoints.http.transport.respondingTimeouts.writeTimeout=30m
--entrypoints.http.transport.respondingTimeouts.idleTimeout=30m
--entrypoints.https.transport.respondingTimeouts.readTimeout=30m
--entrypoints.https.transport.respondingTimeouts.writeTimeout=30m
--entrypoints.https.transport.respondingTimeouts.idleTimeout=30m
```

Restart the Coolify proxy after changing these settings. If Cloudflare is proxying the hostname, large single-request uploads are still limited by the Cloudflare plan's maximum upload size; use a DNS-only upload/API hostname or chunked uploads for files above that limit.

6. **Deploy**
   - Save and deploy the resource. Coolify will build both images and start the stack.

## Health checks

The Compose file defines health checks for:

- API: `http://localhost:8787/health`
- Web: `http://localhost:3000/`

## Data persistence

The API writes job artifacts under `POVERLAY_DATA_DIR` and the Compose file mounts it to a named volume (`pov_data`). Keep this volume intact across deployments to preserve render output and analytics artifacts.
