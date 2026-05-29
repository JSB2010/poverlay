#!/usr/bin/env bash
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-JSB2010/poverlay}"
API_BASE="${POVERLAY_DEPLOYED_API_BASE:-https://poverlay.com}"
WEB_ORIGIN="${POVERLAY_DEPLOYED_WEB_ORIGIN:-https://poverlay.com}"
RELEASE_TAG="${POVERLAY_DESKTOP_RELEASE_TAG:-desktop-beta-20260529-a3b826b}"

failures=0

section() {
  printf '\n== %s ==\n' "$1"
}

pass() {
  printf 'PASS: %s\n' "$1"
}

warn() {
  printf 'WARN: %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1"
  failures=$((failures + 1))
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Missing required command: $1"
    return 1
  fi
}

has_secret() {
  grep -Fxq "$1" <<<"${SECRET_NAMES}"
}

require_secret() {
  if has_secret "$1"; then
    pass "GitHub secret is present: $1"
  else
    fail "GitHub secret is missing: $1"
  fi
}

section "Tooling"
require_command gh
require_command curl
require_command python3

if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  fail "gh is not authenticated for github.com"
fi

SECRET_NAMES="$(gh secret list --repo "${REPO}" | awk '{print $1}' || true)"

section "Hosted Feature State"
META_JSON="$(curl -fsS --max-time 15 "${API_BASE%/}/api/meta")"
if python3 -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("local_render_enabled") else 1)' <<<"${META_JSON}"; then
  pass "Deployed API has local rendering enabled: ${API_BASE}"
else
  fail "Deployed API local rendering is not enabled: ${API_BASE}"
fi

if python3 - "${WEB_ORIGIN}" "${RELEASE_TAG}" <<'PY'
from __future__ import annotations

import re
import sys
import urllib.parse
import urllib.request

origin, release_tag = sys.argv[1:3]
html = urllib.request.urlopen(f"{origin.rstrip('/')}/studio", timeout=15).read().decode("utf-8", "ignore")
chunk_urls = [
    urllib.parse.urljoin(origin, src)
    for src in re.findall(r'(?:src|href)="([^"]+)"', html)
    if "/_next/static/chunks/" in src and src.endswith(".js")
]
for url in chunk_urls:
    try:
        data = urllib.request.urlopen(url, timeout=15).read().decode("utf-8", "ignore")
    except Exception:
        continue
    if release_tag in data:
        raise SystemExit(0)
raise SystemExit(1)
PY
then
  pass "Deployed Studio includes desktop download base for ${RELEASE_TAG}"
else
  fail "Deployed Studio bundle does not include desktop download base for ${RELEASE_TAG}"
fi

section "GitHub Workflows"
if gh run list --repo "${REPO}" --branch main --workflow CI --limit 10 --json conclusion,url,headSha |
  python3 -c 'import json,sys; runs=json.load(sys.stdin); ok=next((r for r in runs if r["conclusion"]=="success"), None); print(ok["url"] if ok else ""); raise SystemExit(0 if ok else 1)'; then
  pass "Latest main CI has a successful run"
else
  fail "No successful recent main CI run found"
fi

if gh run list --repo "${REPO}" --workflow "Deployed Local Render Smoke" --limit 10 --json conclusion,url,headSha |
  python3 -c 'import json,sys; runs=json.load(sys.stdin); ok=next((r for r in runs if r["conclusion"]=="success"), None); print(ok["url"] if ok else ""); raise SystemExit(0 if ok else 1)'; then
  pass "Deployed local-render smoke has a successful run"
else
  fail "No successful deployed local-render smoke run found"
fi

if gh run list --repo "${REPO}" --workflow "Desktop Release" --limit 20 --json conclusion,url,headSha |
  python3 -c 'import json,sys; runs=json.load(sys.stdin); ok=next((r for r in runs if r["conclusion"]=="success"), None); print(ok["url"] if ok else ""); raise SystemExit(0 if ok else 1)'; then
  pass "Desktop release build/smoke has a successful run"
else
  fail "No successful desktop release build/smoke run found"
fi

section "Release Assets"
if gh release view "${RELEASE_TAG}" --repo "${REPO}" --json assets,isPrerelease,url |
  python3 -c '
import json, sys
release = json.load(sys.stdin)
required = {"poverlay-desktop-macos.dmg", "poverlay-desktop-windows.exe", "poverlay-desktop-windows.msi"}
assets = {asset["name"]: asset for asset in release.get("assets", [])}
missing = sorted(required - set(assets))
if missing:
    print("missing=" + ",".join(missing))
    raise SystemExit(1)
print(release["url"])
for name in sorted(required):
    print("{} {}".format(name, assets[name].get("digest", "")))
'; then
  pass "Desktop release assets are present on ${RELEASE_TAG}"
else
  fail "Desktop release assets are missing on ${RELEASE_TAG}"
fi

section "Deployed Smoke Secrets"
require_secret POVERLAY_DEPLOYED_FIREBASE_API_KEY
require_secret POVERLAY_DEPLOYED_FIREBASE_EMAIL
require_secret POVERLAY_DEPLOYED_FIREBASE_PASSWORD

section "Production Signing Secrets"
require_secret APPLE_CERTIFICATE
require_secret APPLE_CERTIFICATE_PASSWORD

if has_secret APPLE_API_KEY && has_secret APPLE_API_ISSUER && has_secret APPLE_API_PRIVATE_KEY; then
  pass "Apple notarization API-key secrets are present"
elif has_secret APPLE_ID && has_secret APPLE_PASSWORD && has_secret APPLE_TEAM_ID; then
  pass "Apple notarization Apple-ID secrets are present"
else
  fail "Apple notarization secrets are missing: set APPLE_API_KEY/APPLE_API_ISSUER/APPLE_API_PRIVATE_KEY or APPLE_ID/APPLE_PASSWORD/APPLE_TEAM_ID"
fi

require_secret WINDOWS_CERTIFICATE
require_secret WINDOWS_CERTIFICATE_PASSWORD

if command -v security >/dev/null 2>&1; then
  if security find-identity -v -p codesigning 2>/dev/null | grep -q "Developer ID Application"; then
    pass "Local keychain has a Developer ID Application identity"
  else
    warn "Local keychain does not show a Developer ID Application identity"
  fi
fi

section "Result"
if ((failures > 0)); then
  printf 'Client-rendering release readiness failed with %s blocking issue(s).\n' "${failures}"
  exit 1
fi

printf 'Client-rendering release readiness passed.\n'
