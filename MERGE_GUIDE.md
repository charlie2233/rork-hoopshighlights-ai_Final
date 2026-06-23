# Upload Pipeline Merge Guide

## Summary

This branch adds an asset-first upload pipeline in the local FastAPI backend and publishes the additive Worker schema needed for UI, detection, and edit agents.

## Key Files

- `ios/backend/app/models.py`: asset/upload API models and job response asset fields.
- `ios/backend/app/upload_storage.py`: local disk and object-storage-compatible upload adapters.
- `ios/backend/app/asset_store.py`: in-memory and Firestore asset stores.
- `ios/backend/app/api.py`: upload init/complete/status routes, proxy-ready gate, and asset-backed inference materialization.
- `ios/backend/tests/test_upload_pipeline.py`: lifecycle coverage.
- `ios/backend/scripts/upload_benchmark.py`: timing and retry/resume benchmark.
- `services/control-plane/src/types.ts`: additive `assetId/storageKey` fields.
- `services/control-plane/src/routes/public.ts`: Worker create/poll payloads expose `assetId`; internal team-scan payloads carry `assetId/storageKey`.
- `services/control-plane/src/queue/consumer.ts`: inference dispatch includes `assetId/storageKey`.

## Detection Agent Notes

- Prefer `assetId` and `storageKey` from inference payloads.
- Treat `sourceUrl` as a migration fallback only.
- Refuse or defer analysis if the asset status is not `proxy_ready` or `ready`.
- Keep object keys and signed URLs out of logs and public errors.

## Edit Agent Notes

- Use `proxyStorageKey` as the source for first-preview/edit planning once asset completion returns artifacts.
- Continue to accept `sourceObjectKey` for existing edit jobs during migration.
- Do not move rendering or edit planning into iOS.

## UI Agent Notes

- Keep old create-job upload path temporarily.
- Add the asset path in parallel:
  `init -> upload -> complete -> poll asset -> analysis-jobs -> poll job`.
- Persist `assetId`, `storageKey`, `uploadMode`, `uploadId`, part count, part size, uploaded parts, and asset status in resume manifests.
- Show a dedicated post-upload state such as `Preparing uploaded video` before starting AI.
- Redact `storageKey`, `sourceObjectKey`, signed URLs, and local paths in proof copy.

## Risk Areas

- Local post-upload processing attempts FFmpeg/ffprobe proxy and thumbnail generation, then falls back safely for invalid local test bytes.
- Managed mode needs a durable post-upload queue; local processing is inline for deterministic tests.
- Worker schema is additive and maps current R2 uploads as `assetId = jobId`; public Worker responses keep `storageKey` redacted while internal provider dispatch maps `storageKey = sourceObjectKey` until a durable Worker asset table exists.

## Verification Commands

```bash
cd /Users/hanfei/hc-agent-upload
PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_upload_pipeline

cd services/control-plane
npm test -- --test-name-pattern upload
npm run typecheck
```
