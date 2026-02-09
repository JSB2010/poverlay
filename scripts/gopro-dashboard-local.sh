#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor/gopro-dashboard-overlay"

if [[ ! -d "$VENDOR" ]]; then
  echo "Missing vendor renderer at $VENDOR" >&2
  exit 1
fi

export PYTHONPATH="$VENDOR${PYTHONPATH:+:$PYTHONPATH}"
exec "$ROOT/.venv/bin/python" "$VENDOR/bin/gopro-dashboard.py" "$@"
