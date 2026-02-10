#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -x .venv/bin/uvicorn ]]; then
  echo "Environment not ready. Run ./scripts/setup.sh first." >&2
  exit 1
fi

exec .venv/bin/uvicorn --app-dir apps/api app.main:app --host 0.0.0.0 --port 8787 --reload
