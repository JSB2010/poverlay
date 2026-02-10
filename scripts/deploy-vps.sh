#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy-vps.sh [--branch <name>] [--skip-check] [--with-system]

Deploy current repo on a VPS using git + systemd.

Options:
  --branch <name>  Branch to deploy (default: current branch)
  --skip-check     Skip pnpm check before restart
  --with-system    Reinstall systemd/nginx config from deploy/ before restart
EOF
}

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
RUN_CHECK=true
WITH_SYSTEM=false

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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      BRANCH="${2:-}"
      shift 2
      ;;
    --skip-check)
      RUN_CHECK=false
      shift
      ;;
    --with-system)
      WITH_SYSTEM=true
      shift
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

if [[ "${WITH_SYSTEM}" == "true" ]]; then
  echo "==> Refreshing system-level config"
  sudo cp deploy/systemd/poverlay-api.service /etc/systemd/system/poverlay-api.service
  sudo cp deploy/systemd/poverlay-web.service /etc/systemd/system/poverlay-web.service
  sudo cp deploy/nginx/poverlay.conf /etc/nginx/sites-available/poverlay
  sudo ln -sf /etc/nginx/sites-available/poverlay /etc/nginx/sites-enabled/poverlay
  sudo nginx -t
  sudo systemctl reload nginx
  sudo systemctl daemon-reload
fi

echo "==> Restarting app services"
sudo systemctl restart poverlay-api poverlay-web

echo "==> Health checks"
wait_for_http "API" "http://127.0.0.1:8787/health"
wait_for_http "Web" "http://127.0.0.1:3000"

echo "Deploy complete."
