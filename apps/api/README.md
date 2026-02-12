# POVerlay API

FastAPI service for render job orchestration.

## Run (dev)

From repo root:

```bash
./scripts/run-api.sh
```

## Tests

From repo root:

```bash
python3 -m pytest apps/api/tests -q
```

## Notes

- Source package: `apps/api/app`
- Main ASGI entrypoint: `app.main:app`
- Local runtime data defaults to `data/` at repository root.
- Override data root with `POVERLAY_DATA_DIR` if needed.
- Runtime config is centralized/validated in `apps/api/app/config.py`.
- Firestore and R2 data contracts are defined in `apps/api/app/contracts.py`.
