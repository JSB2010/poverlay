# Client Rendering

POVerlay supports a beta local-render path where the hosted Studio remains the primary UI and POVerlay Desktop performs rendering on the user's machine.

## Render Targets

- Server render uploads GPX and source clips to the API, queues work on the server, renders with the existing FastAPI worker, uploads outputs to R2, and exposes downloads through the media library.
- Local render creates a hosted job manifest, opens POVerlay Desktop through a `poverlay://` pairing link, renders with the local Python worker and native FFmpeg, and saves output locally.

## Local Render Security Model

- The public API never connects inbound to a user's computer.
- Studio starts a short-lived pairing code with `POST /api/local-render/pairing/start`.
- POVerlay Desktop starts the local worker sidecar on `127.0.0.1:47981`.
- Studio calls the local worker at `POST /pairing/complete`, and the worker completes pairing with `POST /api/local-render/pairing/complete`.
- The local worker accepts pairing only from localhost, `poverlay.com` hosts, or domains configured with `POVERLAY_ALLOWED_WEB_ORIGINS` and `POVERLAY_ALLOWED_API_BASES`.
- The API returns a worker token scoped to the authenticated user.
- The local worker returns a per-session localhost token to Studio.
- Studio sends selected GPX/video files to `POST http://127.0.0.1:47981/jobs` with the localhost token.
- Worker progress updates use `PATCH /api/local-render/jobs/{job_id}` with the worker token.
- Source video bytes are not uploaded to the API during local render.

## Output Storage

Local render defaults to local-only output. Cloud storage is opt-in from Studio and uploads only completed rendered outputs, never source videos.

For media-library upload:

1. The local job is created with `upload_intent: "media_library"`.
2. After a local output is rendered, the worker requests `POST /api/local-render/jobs/{job_id}/upload-target`.
3. The API returns a short-lived R2 `PUT` target for the rendered output filename.
4. The worker uploads the rendered output to R2.
5. The worker calls `POST /api/local-render/jobs/{job_id}/upload-complete`.
6. The API verifies the R2 object and attaches download metadata to the media item.

## Desktop Packaging

The first desktop release targets:

- macOS `.dmg`
- Windows installer `.exe` or `.msi`

Linux support can follow after the macOS and Windows worker packaging path is proven.

The desktop bundle uses a Tauri sidecar named `binaries/poverlay-worker`. Release builds must run `pnpm stage:desktop-sidecar` after the PyInstaller worker build so Tauri receives the required target-triple-suffixed binary under `apps/desktop/src-tauri/binaries/`.

macOS release builds use Tauri's `.app` bundle plus `scripts/package-macos-dmg.sh` to create a simple compressed DMG without Finder AppleScript customization. This is more reliable in CI and local non-interactive build environments.

Packaged desktop builds are smoke-tested before installer artifacts are uploaded. The macOS smoke test launches the built `.app` and the Windows smoke test launches the built desktop `.exe`; both fail unless `http://127.0.0.1:47981/health` reports the bundled `POVerlay Local Worker`.

`pnpm smoke:local-render:http` runs a local HTTP-level local-render smoke test without Firebase, Firestore, R2, or FFmpeg. It starts the FastAPI control API and the Python local worker on localhost, enables the explicit `POVERLAY_LOCAL_SMOKE_AUTH_UID` / `POVERLAY_LOCAL_SMOKE_IN_MEMORY_JOBS` test-only mode, uses mock FFmpeg/renderer binaries, and verifies pairing, local job creation, local worker submission, hosted progress updates, and a completed local output path. CI runs this after the normal monorepo checks so API/worker contract regressions fail before release packaging.

`pnpm smoke:deployed-local-render` performs the same control-plane smoke against a deployed API. Set `POVERLAY_DEPLOYED_API_BASE` to the hosted API origin. For authentication, either set `POVERLAY_DEPLOYED_AUTH_TOKEN` to a valid Firebase ID token or set `POVERLAY_DEPLOYED_FIREBASE_API_KEY`, `POVERLAY_DEPLOYED_FIREBASE_EMAIL`, and `POVERLAY_DEPLOYED_FIREBASE_PASSWORD` so the script can mint a fresh ID token with Firebase's `accounts:signInWithPassword` REST endpoint.

- `POVERLAY_DEPLOYED_WEB_ORIGIN`: Origin header sent to the local worker during pairing; defaults to the API origin.
- `POVERLAY_DEPLOYED_SMOKE_WORKER_PORT`: localhost worker port; defaults to `47981`.
- `POVERLAY_DEPLOYED_SMOKE_START_WORKER`: starts the source Python worker with mock FFmpeg/renderer binaries when true, defaults to true.
- `POVERLAY_DEPLOYED_SMOKE_TIMEOUT_SECONDS`: hosted job polling timeout, defaults to 45 seconds.

This deployed smoke creates a local-only job in the target account. It does not upload source video or rendered output to R2.

GitHub Actions also exposes a `Deployed Local Render Smoke` workflow_dispatch job. Prefer configuring `POVERLAY_DEPLOYED_FIREBASE_API_KEY`, `POVERLAY_DEPLOYED_FIREBASE_EMAIL`, and `POVERLAY_DEPLOYED_FIREBASE_PASSWORD` repository secrets for a disposable smoke-test account; the workflow also accepts `POVERLAY_DEPLOYED_SMOKE_AUTH_TOKEN` if you intentionally want to provide a raw ID token. Then run the workflow with the deployed API origin and optional web origin. The deployed API must have `LOCAL_RENDER_ENABLED=true`, Firestore job persistence enabled, and its worker-origin guardrails must allow the supplied web origin.

The release workflow can run unsigned beta builds, or signed production-style builds when the signing inputs are enabled:

- macOS signing requires `sign_macos=true` plus `APPLE_CERTIFICATE` and `APPLE_CERTIFICATE_PASSWORD` repository secrets. `APPLE_CERTIFICATE` is a base64-encoded Apple Developer ID `.p12`. The workflow imports it into a temporary keychain before running Tauri. `APPLE_SIGNING_IDENTITY` is optional when the workflow can infer the identity from the certificate.
- macOS notarization requires `notarize_macos=true` and `sign_macos=true`. Use either App Store Connect API secrets (`APPLE_API_KEY`, `APPLE_API_ISSUER`, `APPLE_API_PRIVATE_KEY`) or Apple ID secrets (`APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID`). The workflow notarizes and staples the final DMG.
- Windows signing requires `sign_windows=true` plus `WINDOWS_CERTIFICATE` and `WINDOWS_CERTIFICATE_PASSWORD` repository secrets. `WINDOWS_CERTIFICATE` is the base64-encoded `.pfx`; `windows_timestamp_url` defaults to Sectigo and can be overridden per run.

The worker binary also exposes a `dashboard` subcommand that runs the bundled `gopro-dashboard.py` script. Local renders default to invoking the sidecar as `poverlay-worker dashboard ...`, so users do not need a separate `gopro-dashboard.py` installation on PATH. Developers can override this with `POVERLAY_LOCAL_RENDERER_BIN` while testing.

Studio shows desktop installer links only when `NEXT_PUBLIC_DESKTOP_DOWNLOAD_BASE_URL` or the platform-specific `NEXT_PUBLIC_DESKTOP_MACOS_DOWNLOAD_URL` / `NEXT_PUBLIC_DESKTOP_WINDOWS_DOWNLOAD_URL` values are configured. The release workflow publishes predictable asset names:

- `poverlay-desktop-macos.dmg`
- `poverlay-desktop-windows.exe`
- `poverlay-desktop-windows.msi` when Tauri produces an MSI

## Support Notes

Release readiness evidence is tracked in `docs/client-rendering-release-checklist.md`.

If a local render fails, collect:

- POVerlay Desktop version
- Operating system and CPU/GPU model
- FFmpeg encoder selected by the worker
- Render log from the local output/work folder
- Hosted job ID
- Whether the job was local-only or media-library upload
