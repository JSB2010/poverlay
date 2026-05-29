# Client Rendering Release Status

Last updated: 2026-05-29

## Verified

- `main` CI is green at `4af7e3f`: https://github.com/JSB2010/poverlay/actions/runs/26613545164
- Unsigned macOS and Windows desktop build/smoke passed: https://github.com/JSB2010/poverlay/actions/runs/26612758557
- Deployed local-render smoke passed from GitHub Actions: https://github.com/JSB2010/poverlay/actions/runs/26613722635
- Deployed local-render smoke job reached `completed`: `73c6775508ed4d34a969e763b244e091`
- Deployed Studio bundle includes desktop download URLs for `desktop-beta-20260529-a3b826b`.
- Published unsigned desktop prerelease: https://github.com/JSB2010/poverlay/releases/tag/desktop-beta-20260529-a3b826b

## Current Installer Assets

- macOS DMG: `poverlay-desktop-macos.dmg`
  - SHA-256: `d3033f631a90a88b185acca58fff33b7b9a4509417b6f6d211dab71552911a07`
- Windows NSIS EXE: `poverlay-desktop-windows.exe`
  - SHA-256: `c287f287fd57eac7c07518484602a54d03cb101922f3c841e112b77d063a5a92`
- Windows MSI: `poverlay-desktop-windows.msi`
  - SHA-256: `134774427e5cf6464d0b596b6610e40c353312552d12a1b5993037f98dba9b41`

The published macOS DMG was downloaded, mounted, and the app inside it launched the bundled local worker successfully.

## Remaining Production Gates

- Run `Desktop Release` with `sign_macos=true`.
- Run `Desktop Release` with `notarize_macos=true`.
- Run `Desktop Release` with `sign_windows=true`.
- Replace the deployed desktop download base with signed/notarized production assets.
- Perform manual installed-app browser smoke on macOS and Windows with real source media.
