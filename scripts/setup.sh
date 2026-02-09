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
pip install -r requirements.txt

echo "Setup complete. Run: ./scripts/run.sh"
