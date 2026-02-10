#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy-vps.sh [--branch <name>] [--skip-check] [--with-systemd] [--with-nginx] [--public-url <url>]

Deploy current repo on a VPS using git + systemd.

Options:
  --branch <name>   Branch to deploy (default: current branch)
  --skip-check      Skip pnpm check before restart
  --with-systemd    Reinstall systemd service files from deploy/
  --with-nginx      Reinstall nginx site file from deploy/ (guarded if Certbot-managed)
  --public-url <u>  Optional HTTPS URL to verify via Nginx after restart
EOF
}

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
RUN_CHECK=true
WITH_SYSTEMD=false
WITH_NGINX=false
PUBLIC_URL=""
LOCK_FILE="/tmp/poverlay-deploy.lock"

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${cmd}" >&2
    exit 1
  fi
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local retries="${3:-30}"

  for ((i = 1; i <= retries; i++)); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "${name} did not become ready: ${url}" >&2
  return 1
}

show_failure_context() {
  echo "Deploy failed. Current service status:" >&2
  sudo systemctl status --no-pager poverlay-api poverlay-web || true
  echo "--- poverlay-api logs (tail) ---" >&2
  sudo journalctl -u poverlay-api -n 80 --no-pager || true
  echo "--- poverlay-web logs (tail) ---" >&2
  sudo journalctl -u poverlay-web -n 80 --no-pager || true
}

trap show_failure_context ERR

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      if [[ $# -lt 2 ]]; then
        echo "--branch requires a value." >&2
        exit 1
      fi
      BRANCH="${2:-}"
      shift 2
      ;;
    --skip-check)
      RUN_CHECK=false
      shift
      ;;
    --with-systemd)
      WITH_SYSTEMD=true
      shift
      ;;
    --with-system)
      WITH_SYSTEMD=true
      echo "Warning: --with-system is deprecated; use --with-systemd." >&2
      shift
      ;;
    --with-nginx)
      WITH_NGINX=true
      shift
      ;;
    --public-url)
      if [[ $# -lt 2 ]]; then
        echo "--public-url requires a value." >&2
        exit 1
      fi
      PUBLIC_URL="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${BRANCH}" ]]; then
  echo "Branch name cannot be empty." >&2
  exit 1
fi

if [[ -n "${PUBLIC_URL}" && "${PUBLIC_URL}" != http://* && "${PUBLIC_URL}" != https://* ]]; then
  echo "--public-url must start with http:// or https://." >&2
  exit 1
fi

require_cmd git
require_cmd pnpm
require_cmd python3
require_cmd curl
require_cmd sudo

if command -v flock >/dev/null 2>&1; then
  exec 9>"${LOCK_FILE}"
  if ! flock -n 9; then
    echo "Another deployment is already running (lock: ${LOCK_FILE})." >&2
    exit 1
  fi
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit or stash changes before deploy." >&2
  exit 1
fi

echo "==> Fetching latest from origin/${BRANCH}"
git fetch --prune origin
git checkout "${BRANCH}"
git pull --ff-only origin "${BRANCH}"

echo "==> Installing JS dependencies"
pnpm install --frozen-lockfile

echo "==> Ensuring Python environment"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r apps/api/requirements-dev.txt

if [[ "${RUN_CHECK}" == "true" ]]; then
  echo "==> Running checks"
  pnpm check
else
  echo "==> Skipping checks"
  echo "==> Building web"
  pnpm build
fi

if [[ "${WITH_SYSTEMD}" == "true" ]]; then
  echo "==> Refreshing systemd config"
  sudo cp deploy/systemd/poverlay-api.service /etc/systemd/system/poverlay-api.service
  sudo cp deploy/systemd/poverlay-web.service /etc/systemd/system/poverlay-web.service
  sudo systemctl daemon-reload
fi

if [[ "${WITH_NGINX}" == "true" ]]; then
  echo "==> Refreshing nginx config"
  if sudo test -f /etc/nginx/sites-available/poverlay; then
    if sudo grep -q "managed by Certbot" /etc/nginx/sites-available/poverlay && ! grep -q "managed by Certbot" deploy/nginx/poverlay.conf; then
      echo "Refusing to overwrite Certbot-managed nginx config with non-Certbot template." >&2
      echo "Update /etc/nginx/sites-available/poverlay manually or run Certbot again after sync." >&2
      exit 1
    fi
    sudo cp /etc/nginx/sites-available/poverlay "/etc/nginx/sites-available/poverlay.bak.$(date +%Y%m%d%H%M%S)"
  fi
  sudo cp deploy/nginx/poverlay.conf /etc/nginx/sites-available/poverlay
  sudo ln -sf /etc/nginx/sites-available/poverlay /etc/nginx/sites-enabled/poverlay
  sudo nginx -t
  sudo systemctl reload nginx
fi

echo "==> Restarting app services"
sudo systemctl restart poverlay-api poverlay-web

echo "==> Health checks"
wait_for_http "API" "http://127.0.0.1:8787/health"
wait_for_http "Web" "http://127.0.0.1:3000"
if [[ -n "${PUBLIC_URL}" ]]; then
  wait_for_http "Public URL" "${PUBLIC_URL}"
fi

echo "Deploy complete."
