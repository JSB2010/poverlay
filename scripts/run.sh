#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source scripts/load-env.sh

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm is required. Run ./scripts/setup.sh first." >&2
  exit 1
fi

exec pnpm dev
