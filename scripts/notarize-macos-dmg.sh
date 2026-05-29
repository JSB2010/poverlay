#!/usr/bin/env bash
set -euo pipefail

dmg_path="${1:?Usage: notarize-macos-dmg.sh <dmg-path>}"

if [[ ! -f "$dmg_path" ]]; then
  echo "DMG not found: $dmg_path" >&2
  exit 1
fi

auth_args=()
if [[ -n "${APPLE_API_KEY:-}" || -n "${APPLE_API_ISSUER:-}" || -n "${APPLE_API_KEY_PATH:-}" ]]; then
  if [[ -z "${APPLE_API_KEY:-}" || -z "${APPLE_API_ISSUER:-}" || -z "${APPLE_API_KEY_PATH:-}" ]]; then
    echo "APPLE_API_KEY, APPLE_API_ISSUER, and APPLE_API_KEY_PATH are all required for API-key notarization." >&2
    exit 1
  fi
  auth_args=(--key "$APPLE_API_KEY_PATH" --key-id "$APPLE_API_KEY" --issuer "$APPLE_API_ISSUER")
elif [[ -n "${APPLE_ID:-}" || -n "${APPLE_PASSWORD:-}" || -n "${APPLE_TEAM_ID:-}" ]]; then
  if [[ -z "${APPLE_ID:-}" || -z "${APPLE_PASSWORD:-}" || -z "${APPLE_TEAM_ID:-}" ]]; then
    echo "APPLE_ID, APPLE_PASSWORD, and APPLE_TEAM_ID are all required for Apple-ID notarization." >&2
    exit 1
  fi
  auth_args=(--apple-id "$APPLE_ID" --password "$APPLE_PASSWORD" --team-id "$APPLE_TEAM_ID")
else
  echo "No Apple notarization credentials were provided." >&2
  exit 1
fi

xcrun notarytool submit "$dmg_path" --wait "${auth_args[@]}"
xcrun stapler staple "$dmg_path"
xcrun stapler validate "$dmg_path"
