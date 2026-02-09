# Vendored Dependency

This project vendors `gopro-dashboard-overlay` for local modifications and deterministic behavior.

- Upstream repository: `https://github.com/time4tea/gopro-dashboard-overlay`
- Upstream commit: `0b7c0e8f302275cb2f1f95433ec99f2591a2da75`
- Vendored path: `vendor/gopro-dashboard-overlay`

Local modifications were made to support:
- GPX-only overlay framerate matching source FPS
- Additional overlay FPS controls used by the app

Repository hygiene:
- Non-runtime upstream folders (tests/docs/examples/CI/build scripts) were removed from the vendored copy to keep this repo lean.
- Runtime-required components kept: `bin/` and `gopro_overlay/` plus license/readme metadata.
