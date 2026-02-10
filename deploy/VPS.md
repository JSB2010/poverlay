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

Create `/etc/poverlay/poverlay.env`:

```bash
sudo mkdir -p /etc/poverlay
cat <<'ENV' | sudo tee /etc/poverlay/poverlay.env
API_PROXY_TARGET=http://127.0.0.1:8787
CORS_ORIGINS=https://your-domain.com,http://localhost:3000,http://127.0.0.1:3000
JOB_OUTPUT_RETENTION_HOURS=24
JOB_CLEANUP_INTERVAL_SECONDS=900
DELETE_INPUTS_ON_COMPLETE=true
DELETE_WORK_ON_COMPLETE=true
ENV
```

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

## Ongoing deploys (git-first workflow)

Run this on the VPS from `/opt/poverlay`:

```bash
./scripts/deploy-vps.sh --branch main --public-url https://poverlay.com
```

Notes:

- This does a safe `git pull --ff-only` (no hard reset by default).
- By default it runs `pnpm check` (which includes build), then restarts services.
- Use `--skip-check` for faster deploys when needed.
- Use `--with-systemd` when you change `deploy/systemd/*`.
- Use `--with-nginx` only when you intentionally want to sync `deploy/nginx/poverlay.conf`.
- If your VPS nginx file is Certbot-managed, `--with-nginx` will refuse to overwrite it unless templates match Certbot layout.

## GitHub Actions auto-deploy

`.github/workflows/deploy.yml` can deploy automatically after CI passes on pushes to `main` (or manually via workflow dispatch).

Set these repository secrets:

- `VPS_HOST` (example: `15.204.223.62`)
- `VPS_USER` (example: `ubuntu`)
- `VPS_SSH_KEY` (private key contents)
- `VPS_PORT` (optional, defaults to `22`)

Optional repository variables:

- `VPS_APP_DIR` (defaults to `/opt/poverlay`)
- `VPS_PUBLIC_URL` (defaults to `https://poverlay.com`)

The workflow assumes the remote user can run `sudo -n` non-interactively.
