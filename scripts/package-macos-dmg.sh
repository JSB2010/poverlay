#!/usr/bin/env bash
set -euo pipefail

app_path="${1:?Usage: package-macos-dmg.sh <app-path> <output-dmg>}"
output_dmg="${2:?Usage: package-macos-dmg.sh <app-path> <output-dmg>}"

if [[ ! -d "$app_path" ]]; then
  echo "App bundle not found: $app_path" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

volume_root="$tmp_dir/POVerlay Desktop"
mkdir -p "$volume_root"
cp -R "$app_path" "$volume_root/"
ln -s /Applications "$volume_root/Applications"

mkdir -p "$(dirname "$output_dmg")"
rm -f "$output_dmg"
hdiutil create \
  -volname "POVerlay Desktop" \
  -srcfolder "$volume_root" \
  -ov \
  -format UDZO \
  "$output_dmg"
