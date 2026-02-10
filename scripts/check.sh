#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

pnpm check:web
pnpm build

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv Python. Run ./scripts/setup.sh first." >&2
  exit 1
fi

.venv/bin/python -m py_compile apps/api/app/main.py apps/api/app/gpx_tools.py apps/api/app/layouts.py
.venv/bin/python -m pytest apps/api/tests -q
