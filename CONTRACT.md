# HoopClips Agent A Contract

## Asset-First Upload

Canonical upload state is represented by `AssetRecord` and additive DTO fields named `assetId` and `storageKey`. During migration, legacy job fields stay valid: `jobId`, `uploadUrl`, `sourceObjectKey`, `resultObjectKey`, `sourceUrl`, and `/v1/analysis/jobs/{jobId}/start` remain supported.

Canonical route order:

1. `POST /v1/uploads/init`
2. Signed upload to the returned `uploadUrl`
3. `POST /v1/uploads/{assetId}/complete`
4. `GET /v1/assets/{assetId}` until `status` is `proxy_ready` or `ready`
5. `POST /v1/assets/{assetId}/team-scan` or `POST /v1/assets/{assetId}/analysis-jobs`

Asset status values are `initialized`, `uploading`, `uploaded`, `processing`, `proxy_ready`, `ready`, and `failed`.

`AssetRecord` fields:

- `assetId`
- `installId`
- `filename`
- `contentType`
- `fileSizeBytes`
- `durationSeconds`
- `storageKey`
- `status`
- `uploadMode`
- `uploadedBytes`
- `artifacts.proxyStorageKey`
- `artifacts.thumbnailStorageKeys`
- `artifacts.waveformStorageKey`
- `createdAt`
- `updatedAt`
- `failureReason`

## Clip Accuracy Review

Canonical review feedback tags are:

- `duplicate`
- `wrong_team`
- `bad_window`
- `wrong_label`
- `low_quality`

These tags must persist from iOS review edits through backend edit DTOs, Worker admin clip review updates, and evaluation fixtures.

Benchmark metrics:

- `recallAtK`
- `precisionAtK`
- `boundaryErrorSeconds`
- `duplicateRate`

## Architecture Boundary

The iOS app remains the control surface for upload, queue status, review, preview, download, and share/export handoff. Production video analysis, AI edit planning, and rendering remain backend-owned.
