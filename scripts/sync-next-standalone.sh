#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

WEB_DIR="apps/web"
NEXT_DIR="${WEB_DIR}/.next"
STANDALONE_WEB_DIR="${NEXT_DIR}/standalone/apps/web"
STANDALONE_NEXT_DIR="${STANDALONE_WEB_DIR}/.next"

if [[ ! -d "${NEXT_DIR}/standalone" ]]; then
  echo "Missing ${NEXT_DIR}/standalone. Run a web build first." >&2
  exit 1
fi

if [[ ! -d "${NEXT_DIR}/static" ]]; then
  echo "Missing ${NEXT_DIR}/static. Build output is incomplete." >&2
  exit 1
fi

mkdir -p "${STANDALONE_NEXT_DIR}"
rm -rf "${STANDALONE_NEXT_DIR}/static"
cp -R "${NEXT_DIR}/static" "${STANDALONE_NEXT_DIR}/static"

if [[ -d "${WEB_DIR}/public" ]]; then
  rm -rf "${STANDALONE_WEB_DIR}/public"
  cp -R "${WEB_DIR}/public" "${STANDALONE_WEB_DIR}/public"
fi

echo "Standalone assets synced to ${STANDALONE_WEB_DIR}"
