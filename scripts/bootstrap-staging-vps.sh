#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/poverlay-staging}"
BRANCH="${BRANCH:-main}"
DOMAIN="${DOMAIN:-dev.poverlay.com}"
EMAIL="${EMAIL:-jacobsamuelbarkin@gmail.com}"
SITE_NAME="${SITE_NAME:-poverlay-dev}"
ENV_FILE="${ENV_FILE:-/etc/poverlay/poverlay-staging.env}"
PUBLIC_URL="${PUBLIC_URL:-https://${DOMAIN}}"
API_PORT="${API_PORT:-8788}"
WEB_PORT="${WEB_PORT:-3001}"
SKIP_CERTBOT="${SKIP_CERTBOT:-false}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_URL="$(git -C "${REPO_ROOT}" remote get-url origin)"

if [[ -z "${REPO_URL}" ]]; then
  echo "Unable to determine git remote URL." >&2
  exit 1
fi

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing command: ${cmd}" >&2
    exit 1
  fi
}

require_cmd git
require_cmd sudo
require_cmd nginx
require_cmd curl

if [[ ! -d "${APP_DIR}/.git" ]]; then
  echo "==> Cloning repo into ${APP_DIR}"
  sudo mkdir -p "${APP_DIR}"
  sudo chown -R "$USER":"$USER" "${APP_DIR}"
  git clone "${REPO_URL}" "${APP_DIR}"
fi

echo "==> Updating staging repository"
git -C "${APP_DIR}" fetch --prune origin
git -C "${APP_DIR}" checkout "${BRANCH}"
git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"

echo "==> Ensuring staging environment file"
sudo mkdir -p "$(dirname "${ENV_FILE}")"
if ! sudo test -f "${ENV_FILE}"; then
  cat <<ENV | sudo tee "${ENV_FILE}" >/dev/null
WEB_BASE_URL=https://${DOMAIN}
API_BASE_URL=https://${DOMAIN}/api
NEXT_PUBLIC_SITE_URL=https://${DOMAIN}
API_PROXY_TARGET=http://127.0.0.1:${API_PORT}
CORS_ORIGINS=https://poverlay.com,https://${DOMAIN},http://localhost:${WEB_PORT},http://127.0.0.1:${WEB_PORT}
JOB_OUTPUT_RETENTION_HOURS=24
JOB_CLEANUP_INTERVAL_SECONDS=900
JOB_CLEANUP_ENABLED=true
DELETE_INPUTS_ON_COMPLETE=true
DELETE_WORK_ON_COMPLETE=true
ENV
fi

echo "==> Installing staging systemd services"
sudo cp "${APP_DIR}/deploy/systemd/poverlay-staging-api.service" /etc/systemd/system/poverlay-staging-api.service
sudo cp "${APP_DIR}/deploy/systemd/poverlay-staging-web.service" /etc/systemd/system/poverlay-staging-web.service
sudo systemctl daemon-reload
sudo systemctl enable poverlay-staging-api poverlay-staging-web >/dev/null

echo "==> Installing staging nginx site"
sudo cp "${APP_DIR}/deploy/nginx/poverlay-dev.conf" "/etc/nginx/sites-available/${SITE_NAME}"
sudo ln -sf "/etc/nginx/sites-available/${SITE_NAME}" "/etc/nginx/sites-enabled/${SITE_NAME}"
sudo nginx -t
sudo systemctl reload nginx

if [[ "${SKIP_CERTBOT}" != "true" ]]; then
  if command -v certbot >/dev/null 2>&1; then
    if ! sudo test -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"; then
      echo "==> Requesting TLS certificate for ${DOMAIN}"
      sudo certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --email "${EMAIL}" --redirect
    fi
  else
    echo "certbot not found; skipping certificate setup." >&2
  fi
fi

echo "==> Running first staging deploy"
cd "${APP_DIR}"
./scripts/deploy-vps.sh \
  --branch "${BRANCH}" \
  --api-service poverlay-staging-api \
  --web-service poverlay-staging-web \
  --api-health-url "http://127.0.0.1:${API_PORT}/health" \
  --web-health-url "http://127.0.0.1:${WEB_PORT}" \
  --public-url "${PUBLIC_URL}"

echo "Staging bootstrap complete."
