#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy-vps.sh [--branch <name>] [--skip-check] [--with-systemd] [--with-nginx] [--public-url <url>]
                              [--api-service <name>] [--web-service <name>]
                              [--api-health-url <url>] [--web-health-url <url>]
                              [--env-file <path>]
                              [--systemd-api-unit <path>] [--systemd-web-unit <path>]
                              [--nginx-site-source <path>] [--nginx-site-name <name>]

Deploy current repo on a VPS using git + systemd.

Options:
  --branch <name>   Branch to deploy (default: current branch)
  --skip-check      Skip pnpm check before restart
  --with-systemd    Reinstall systemd service files from deploy/
  --with-nginx      Reinstall nginx site file from deploy/ (guarded if Certbot-managed)
  --public-url <u>  Optional HTTPS URL to verify via Nginx after restart
  --api-service     systemd service name for API (default: poverlay-api)
  --web-service     systemd service name for web (default: poverlay-web)
  --api-health-url  API health URL (default: http://127.0.0.1:8787/health)
  --web-health-url  Web health URL (default: http://127.0.0.1:3000)
  --env-file        Environment file used for web build/check (default: auto-detect from API service name)
  --systemd-api-unit  source unit file to install when --with-systemd is used
  --systemd-web-unit  source unit file to install when --with-systemd is used
  --nginx-site-source source nginx file to install when --with-nginx is used
  --nginx-site-name   nginx site filename under /etc/nginx/sites-available
EOF
}

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
RUN_CHECK=true
WITH_SYSTEMD=false
WITH_NGINX=false
PUBLIC_URL=""
LOCK_FILE="/tmp/poverlay-deploy.lock"
API_SERVICE="poverlay-api"
WEB_SERVICE="poverlay-web"
API_HEALTH_URL="http://127.0.0.1:8787/health"
WEB_HEALTH_URL="http://127.0.0.1:3000"
SYSTEMD_API_UNIT="deploy/systemd/poverlay-api.service"
SYSTEMD_WEB_UNIT="deploy/systemd/poverlay-web.service"
NGINX_SITE_SOURCE="deploy/nginx/poverlay.conf"
NGINX_SITE_NAME="poverlay"
ENV_FILE=""

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
  sudo systemctl status --no-pager "${API_SERVICE}" "${WEB_SERVICE}" || true
  echo "--- ${API_SERVICE} logs (tail) ---" >&2
  sudo journalctl -u "${API_SERVICE}" -n 80 --no-pager || true
  echo "--- ${WEB_SERVICE} logs (tail) ---" >&2
  sudo journalctl -u "${WEB_SERVICE}" -n 80 --no-pager || true
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
    --api-service)
      if [[ $# -lt 2 ]]; then
        echo "--api-service requires a value." >&2
        exit 1
      fi
      API_SERVICE="${2:-}"
      shift 2
      ;;
    --web-service)
      if [[ $# -lt 2 ]]; then
        echo "--web-service requires a value." >&2
        exit 1
      fi
      WEB_SERVICE="${2:-}"
      shift 2
      ;;
    --api-health-url)
      if [[ $# -lt 2 ]]; then
        echo "--api-health-url requires a value." >&2
        exit 1
      fi
      API_HEALTH_URL="${2:-}"
      shift 2
      ;;
    --web-health-url)
      if [[ $# -lt 2 ]]; then
        echo "--web-health-url requires a value." >&2
        exit 1
      fi
      WEB_HEALTH_URL="${2:-}"
      shift 2
      ;;
    --env-file)
      if [[ $# -lt 2 ]]; then
        echo "--env-file requires a value." >&2
        exit 1
      fi
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --systemd-api-unit)
      if [[ $# -lt 2 ]]; then
        echo "--systemd-api-unit requires a value." >&2
        exit 1
      fi
      SYSTEMD_API_UNIT="${2:-}"
      shift 2
      ;;
    --systemd-web-unit)
      if [[ $# -lt 2 ]]; then
        echo "--systemd-web-unit requires a value." >&2
        exit 1
      fi
      SYSTEMD_WEB_UNIT="${2:-}"
      shift 2
      ;;
    --nginx-site-source)
      if [[ $# -lt 2 ]]; then
        echo "--nginx-site-source requires a value." >&2
        exit 1
      fi
      NGINX_SITE_SOURCE="${2:-}"
      shift 2
      ;;
    --nginx-site-name)
      if [[ $# -lt 2 ]]; then
        echo "--nginx-site-name requires a value." >&2
        exit 1
      fi
      NGINX_SITE_NAME="${2:-}"
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

if [[ "${API_HEALTH_URL}" != http://* && "${API_HEALTH_URL}" != https://* ]]; then
  echo "--api-health-url must start with http:// or https://." >&2
  exit 1
fi

if [[ "${WEB_HEALTH_URL}" != http://* && "${WEB_HEALTH_URL}" != https://* ]]; then
  echo "--web-health-url must start with http:// or https://." >&2
  exit 1
fi

if [[ -z "${API_SERVICE}" || -z "${WEB_SERVICE}" ]]; then
  echo "--api-service and --web-service must be non-empty." >&2
  exit 1
fi

if [[ -z "${NGINX_SITE_NAME}" ]]; then
  echo "--nginx-site-name must be non-empty." >&2
  exit 1
fi

if [[ -z "${ENV_FILE}" && "${API_SERVICE}" =~ ^(.+)-api$ ]]; then
  candidate="/etc/poverlay/${BASH_REMATCH[1]}.env"
  if [[ -r "${candidate}" ]]; then
    ENV_FILE="${candidate}"
  fi
fi

if [[ -n "${ENV_FILE}" ]]; then
  if [[ ! -r "${ENV_FILE}" ]]; then
    echo "Environment file is not readable: ${ENV_FILE}" >&2
    exit 1
  fi
  export POVERLAY_ENV_FILE="${ENV_FILE}"
  echo "==> Using env file for build/check: ${POVERLAY_ENV_FILE}"
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
  if [[ ! -f "${SYSTEMD_API_UNIT}" || ! -f "${SYSTEMD_WEB_UNIT}" ]]; then
    echo "Systemd unit file not found." >&2
    exit 1
  fi
  sudo cp "${SYSTEMD_API_UNIT}" "/etc/systemd/system/${API_SERVICE}.service"
  sudo cp "${SYSTEMD_WEB_UNIT}" "/etc/systemd/system/${WEB_SERVICE}.service"
  sudo systemctl daemon-reload
fi

if [[ "${WITH_NGINX}" == "true" ]]; then
  echo "==> Refreshing nginx config"
  if [[ ! -f "${NGINX_SITE_SOURCE}" ]]; then
    echo "Nginx site source file not found: ${NGINX_SITE_SOURCE}" >&2
    exit 1
  fi
  if sudo test -f "/etc/nginx/sites-available/${NGINX_SITE_NAME}"; then
    if sudo grep -q "managed by Certbot" "/etc/nginx/sites-available/${NGINX_SITE_NAME}" && ! grep -q "managed by Certbot" "${NGINX_SITE_SOURCE}"; then
      echo "Refusing to overwrite Certbot-managed nginx config with non-Certbot template." >&2
      echo "Update /etc/nginx/sites-available/${NGINX_SITE_NAME} manually or run Certbot again after sync." >&2
      exit 1
    fi
    sudo cp "/etc/nginx/sites-available/${NGINX_SITE_NAME}" "/etc/nginx/sites-available/${NGINX_SITE_NAME}.bak.$(date +%Y%m%d%H%M%S)"
  fi
  sudo cp "${NGINX_SITE_SOURCE}" "/etc/nginx/sites-available/${NGINX_SITE_NAME}"
  sudo ln -sf "/etc/nginx/sites-available/${NGINX_SITE_NAME}" "/etc/nginx/sites-enabled/${NGINX_SITE_NAME}"
  sudo nginx -t
  sudo systemctl reload nginx
fi

echo "==> Restarting app services"
sudo systemctl restart "${API_SERVICE}" "${WEB_SERVICE}"

echo "==> Health checks"
wait_for_http "API" "${API_HEALTH_URL}"
wait_for_http "Web" "${WEB_HEALTH_URL}"
if [[ -n "${PUBLIC_URL}" ]]; then
  wait_for_http "Public URL" "${PUBLIC_URL}"
fi

echo "Deploy complete."
