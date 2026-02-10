#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "Installing ffmpeg with Homebrew..."
    brew install ffmpeg
  else
    echo "ffmpeg is required but was not found. Please install ffmpeg and rerun setup." >&2
    exit 1
  fi
fi

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r apps/api/requirements-dev.txt

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required for the web app. Install Node.js 20+ and rerun setup." >&2
  exit 1
fi

if command -v corepack >/dev/null 2>&1; then
  corepack enable >/dev/null 2>&1 || true
  corepack prepare pnpm@9.15.4 --activate >/dev/null 2>&1 || true
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm is required. Install pnpm and rerun setup." >&2
  exit 1
fi

pnpm install

echo "Setup complete. Run: ./scripts/run.sh"
