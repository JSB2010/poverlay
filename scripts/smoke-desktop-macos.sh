#!/usr/bin/env bash
set -euo pipefail

app_path="${1:?Usage: smoke-desktop-macos.sh <app-path>}"
health_url="${2:-http://127.0.0.1:47981/health}"

if [[ ! -d "$app_path" ]]; then
  echo "App bundle not found: $app_path" >&2
  exit 1
fi

if curl -fsS --max-time 1 "$health_url" >/dev/null 2>&1; then
  echo "Local worker health endpoint is already responding before app launch: $health_url" >&2
  exit 1
fi

executable="$(
  find "$app_path/Contents/MacOS" -maxdepth 1 -type f -perm -111 ! -name "poverlay-worker" | head -n 1
)"

if [[ -z "$executable" ]]; then
  echo "No executable found in $app_path/Contents/MacOS" >&2
  exit 1
fi

log_file="$(mktemp -t poverlay-desktop-smoke.XXXXXX.log)"
app_pid=""

cleanup() {
  if [[ -n "$app_pid" ]] && kill -0 "$app_pid" >/dev/null 2>&1; then
    kill "$app_pid" >/dev/null 2>&1 || true
    wait "$app_pid" >/dev/null 2>&1 || true
  fi
  pkill -f "poverlay-worker.*serve.*47981" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$executable" >"$log_file" 2>&1 &
app_pid="$!"

for _ in $(seq 1 60); do
  if ! kill -0 "$app_pid" >/dev/null 2>&1; then
    echo "Desktop app exited before worker became healthy. Log follows:" >&2
    cat "$log_file" >&2
    exit 1
  fi

  health_payload="$(curl -fsS --max-time 1 "$health_url" 2>/dev/null || true)"
  if [[ "$health_payload" == *"POVerlay Local Worker"* ]]; then
    echo "POVerlay Desktop launched worker successfully."
    exit 0
  fi

  sleep 1
done

echo "Timed out waiting for local worker health endpoint. App log follows:" >&2
cat "$log_file" >&2
exit 1
