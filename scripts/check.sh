#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source scripts/load-env.sh

pnpm install --frozen-lockfile
pnpm check:web
pnpm check:desktop
pnpm build

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv Python. Run ./scripts/setup.sh first." >&2
  exit 1
fi

.venv/bin/python -m py_compile apps/api/app/main.py apps/api/app/gpx_tools.py apps/api/app/layouts.py apps/local-worker/poverlay_worker/api_client.py apps/local-worker/poverlay_worker/main.py apps/local-worker/poverlay_worker/profiles.py apps/local-worker/poverlay_worker/render.py apps/local-worker/poverlay_worker/service.py apps/local-worker/poverlay_worker/upload.py scripts/smoke-local-render-http.py scripts/smoke-deployed-local-render.py
.venv/bin/python -m pytest apps/api/tests -q
PYTHONPATH=apps/local-worker .venv/bin/python -m pytest apps/local-worker/tests -q
