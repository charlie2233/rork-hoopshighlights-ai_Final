# Agent A Integration TODO

## Done In This Branch

- [x] Add canonical asset DTOs to iOS, backend, and Worker compatibility layers.
- [x] Keep legacy job-first fields/routes during migration.
- [x] Add reusable `uploads.queue.*` queue model for Agent C UI.
- [x] Persist five canonical review feedback tags end-to-end.
- [x] Add clip-accuracy calibration metrics and fixtures.
- [x] Run focused Agent A tests.

## Agent B Coordination

- Use schema names `AssetRecord`, `assetId`, `storageKey`, `UploadInitResponse`, `AssetStatusResponse`, and `AssetAnalysisJobResponse`.
- Treat Worker R2 legacy jobs as migration-compatible assets where `assetId` can equal `jobId` and internal `storageKey` maps to `sourceObjectKey`.
- Keep public object keys redacted unless an existing legacy endpoint already returns them.

## Agent C Coordination

- Reuse `UploadQueueProjection`, `UploadQueueItem`, and `UploadAssetQueueContract`.
- Use UX/accessibility namespace `uploads.queue.*`.
- Preserve existing identifiers such as `analysis.startButton`, `analysis.resumePendingBackgroundUploadButton`, `analysis.pipeline.resumeUploadButton`, and `settings.backgroundUpload.status`.
