# Client Rendering Release Checklist

Use this checklist before calling client-side rendering production-ready.

## Hosted Environment

- `LOCAL_RENDER_ENABLED=true` is set on the deployed API.
- Firestore job persistence is enabled on the deployed API.
- R2 is enabled if the media-library checkbox will be exposed to users.
- `NEXT_PUBLIC_DESKTOP_DOWNLOAD_BASE_URL` or platform-specific desktop download URLs are set on the deployed web app.
- The desktop worker allow lists permit the deployed web/API origins through `POVERLAY_ALLOWED_WEB_ORIGINS` and `POVERLAY_ALLOWED_API_BASES` when those origins are not under `poverlay.com`.

## Deployed Smoke

Run the `Deployed Local Render Smoke` workflow with:

- `api_base`: deployed API origin.
- `web_origin`: deployed web origin when different from `api_base`.
- Repository secrets:
  - Preferred: `POVERLAY_DEPLOYED_FIREBASE_API_KEY`, `POVERLAY_DEPLOYED_FIREBASE_EMAIL`, `POVERLAY_DEPLOYED_FIREBASE_PASSWORD`.
  - Fallback: `POVERLAY_DEPLOYED_SMOKE_AUTH_TOKEN`.

Passing evidence:

- The workflow completes successfully.
- The workflow log includes `Deployed local-render smoke passed`.
- The created smoke job reaches `completed`.

## Desktop Release

Run the `Desktop Release` workflow.

Minimum beta evidence:

- macOS worker sidecar builds on `macos-14`.
- Windows worker sidecar builds on `windows-latest`.
- macOS desktop app builds and `Smoke test macOS desktop app` passes.
- Windows desktop app builds and `Smoke test Windows desktop app` passes.
- Release artifacts include `poverlay-desktop-macos.dmg` and `poverlay-desktop-windows.exe`; MSI is included when produced.

Production distribution evidence:

- `sign_macos=true` build passes `Verify macOS code signature`.
- `notarize_macos=true` build passes DMG notarization and stapling.
- `sign_windows=true` build passes `Verify Windows signatures`.

## Manual Browser Smoke

Use an installed desktop app and the deployed Studio:

- Select `This computer`.
- Pair the desktop app from the browser.
- Render one small clip as local-only.
- Confirm source video bytes are not uploaded to the API.
- Confirm hosted progress reaches `completed`.
- Confirm the rendered file exists locally.
- Repeat with `Save finished local renders to my media library` enabled when R2 is configured.

## Rollback

- Set `LOCAL_RENDER_ENABLED=false` on the API to hide local rendering from Studio metadata and reject local-render endpoints.
- Keep server rendering enabled as the fallback path.
