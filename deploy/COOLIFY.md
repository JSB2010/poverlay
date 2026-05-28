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
     - `NEXT_PUBLIC_API_BASE` (e.g., `https://poverlay.com/api`)
     - `CORS_ORIGINS` (include your public domain)
   - Recommended values:
     - `API_PROXY_TARGET=http://api:8787`
     - `NEXT_PROXY_CLIENT_MAX_BODY_SIZE=64gb`
   - Set **Build + Runtime** for `NEXT_PUBLIC_*`, `API_PROXY_TARGET`, and `NEXT_PROXY_CLIENT_MAX_BODY_SIZE`.
   - Set **Runtime only** for secrets (Firebase admin keys, R2 keys, Brevo, etc).

5. **Domains**
   - Assign your public domain to the **web** service and set the port to **3000**.
   - Keep the **api** service private (no domain).

6. **Deploy**
   - Save and deploy the resource. Coolify will build both images and start the stack.

## Health checks

The Compose file defines health checks for:

- API: `http://localhost:8787/health`
- Web: `http://localhost:3000/`

## Data persistence

The API writes job artifacts under `POVERLAY_DATA_DIR` and the Compose file mounts it to a named volume (`pov_data`). Keep this volume intact across deployments to preserve render output and analytics artifacts.
