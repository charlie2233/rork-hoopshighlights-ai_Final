# HoopClips Workflow And Upload Contract

This integration branch combines the asset-first upload pipeline, Agent A's accuracy foundations, Agent B's AI Edit engine contracts, and the workflow-first iOS shell. It keeps the backend/client contracts canonical and treats new UI state as projections over those contracts, not as forked payloads.

## Primary Workflow Sections

The iOS app exposes four primary workflow sections:

1. Uploads
2. Review
3. AI Edit
4. Exports

History and Settings remain reachable as secondary utility surfaces from the app shell.

## Canonical Inputs

The UI consumes existing contracts instead of inventing local payloads:

- Upload and analysis job state: `ios/HoopsClips/HoopsClips/Models/CloudAnalysisTypes.swift`
- Asset upload client flow: `ios/HoopsClips/HoopsClips/Services/CloudAnalysisService.swift`
- Clip review state: `ios/HoopsClips/HoopsClips/Models/Clip.swift`
- AI Edit request, plan, render, history, and download state: `ios/HoopsClips/HoopsClips/Models/CloudEditTypes.swift`
- Local backend asset routes: `ios/backend/app/api.py`
- Editing backend plan and render ownership: `ios/backend/app/editing.py`
- Worker additive asset fields: `services/control-plane/src/types.ts`
- Durable render job status: `services/editing/editing_app/models.py`

## Asset Upload Lifecycle

The upload-agent contract is asset-first. Upload, team scan, cloud analysis, and edit planning should not start expensive backend work until an asset reaches `proxy_ready` or `ready`.

Status order:

1. `initialized`
2. `uploading`
3. `uploaded`
4. `processing`
5. `proxy_ready`
6. `ready`, `failed`, or `cancelled`

Canonical asset state is represented by `AssetRecord`/`CloudAssetStatusResponse` and additive DTO fields named `assetId`, `storageKey`, `sourceObjectKey`, `proxyKey`, and `proxyStorageKey`. During migration, legacy job fields stay valid: `jobId`, `uploadUrl`, `sourceObjectKey`, `resultObjectKey`, `sourceUrl`, and `/v1/analysis/jobs/{jobId}/start` remain supported. New asset fields are authoritative when present; legacy job/source fields are compatibility projections.

`AssetRecord` fields:

- `assetId`
- `installId`
- `filename`
- `contentType`
- `fileSizeBytes`
- `durationSeconds`
- `storageKey`
- `sourceObjectKey`
- `proxyKey`
- `status`
- `uploadMode`
- `uploadedBytes`
- `progress`
- `checksumSha256`
- `integrityStatus`
- `analysisJobId`
- `artifacts.proxyStorageKey`
- `artifacts.thumbnailStorageKeys`
- `artifacts.waveformStorageKey`
- `renderAttachments`
- `retryCount`
- `retryable`
- `lastErrorCode`
- `cancellationReason`
- `cancelledAt`
- `createdAt`
- `updatedAt`
- `failureReason`

`integrityStatus` is `pending`, `verified`, `mismatch`, or `unavailable`. Local upload emulation verifies SHA-256 and declared byte length; object-storage deployments preserve the fields and may report `unavailable` when the provider does not expose a SHA-256 checksum. Cancelled assets use status `cancelled`, `failureReason=cancelled`, `lastErrorCode=cancelled`, and `retryable=false`.

## Upload Capabilities

`GET /v1/uploads/capabilities` and `GET /v1/analysis/capabilities` expose structured upload limits and behavior flags:

- `maxFileSizeBytes`
- `maxDurationSeconds`
- `supportsMultipartUpload`
- `supportsResumableUpload`
- `multipartThresholdBytes`
- `resumableUploadThresholdBytes`
- `recommendedPartSizeBytes`
- `minPartSizeBytes`
- `maxPartSizeBytes`
- `maxConcurrentPartUploads`
- `signedUploadTtlSeconds`
- `defaultPollAfterSeconds`
- `supportsChecksumSha256`
- `supportsCancellation`
- `supportsIdempotentComplete`

The iOS client persists the latest structured capability policy from `GET /v1/analysis/capabilities` and applies `maxConcurrentPartUploads` as the server-side ceiling for multipart lanes, with network conditions still allowed to reduce concurrency further. Capability summaries must not include signed URLs, object keys, upload IDs, or local file paths.

## Upload Init

`POST /v1/uploads/init`

Request:

```json
{
  "filename": "game.mp4",
  "contentType": "video/mp4",
  "fileSizeBytes": 12345678,
  "durationSeconds": 120.5,
  "installId": "install-123456",
  "appVersion": "1.0",
  "analysisVersion": "cloud-v1",
  "uploadPreference": "auto",
  "partSizeBytes": 8388608
}
```

Response:

```json
{
  "assetId": "asset_...",
  "storageKey": "assets/asset_.../source/game.mp4",
  "status": "initialized",
  "uploadMode": "single",
  "uploadUrl": "http://127.0.0.1:8080/v1/internal/assets/asset_.../upload",
  "uploadMethod": "PUT",
  "uploadHeaders": {"Content-Type": "video/mp4"},
  "multipart": null,
  "expiresAt": "2026-06-23T08:00:00Z",
  "pollAfterSeconds": 1,
  "uploadState": "waiting_for_client_upload"
}
```

Multipart responses keep the same top-level fields and include `multipart.uploadId`, `partSizeBytes`, `partCount`, and signed part targets.

## Upload Complete

`POST /v1/uploads/{assetId}/complete`

Single-part request:

```json
{"installId": "install-123456"}
```

Multipart request:

```json
{
  "installId": "install-123456",
  "uploadId": "local-asset_...",
  "parts": [
    {"partNumber": 1, "etag": "etag-1", "sizeBytes": 8388608}
  ]
}
```

Response:

```json
{
  "assetId": "asset_...",
  "storageKey": "assets/asset_.../source/game.mp4",
  "sourceObjectKey": "assets/asset_.../source/game.mp4",
  "proxyKey": null,
  "status": "processing",
  "progress": 0.86,
  "checksumSha256": "optional_sha256",
  "integrityStatus": "verified",
  "retryCount": 0,
  "retryable": true,
  "lastErrorCode": null,
  "artifacts": {
    "proxyStorageKey": null,
    "thumbnailStorageKeys": [],
    "waveformStorageKey": null
  },
  "pollAfterSeconds": 1
}
```

Managed runtimes enqueue post-upload proxy/thumbnail/waveform generation through Cloud Tasks at `POST /v1/internal/assets/{assetId}/process`, so `/complete` can return `processing` while the client polls `GET /v1/assets/{assetId}`. Local runtimes use the same dispatcher interface with an inline emulator, so local tests may still observe `proxy_ready` directly from `/complete`.

`/complete` is idempotent once an asset is `processing`, `proxy_ready`, or `ready`. Multipart completion can be retried with an empty `parts` list when the asset already has uploaded part ETags stored. Missing parts and upload ID mismatches keep the asset retryable and update `retryCount` plus `lastErrorCode`.

## Asset Poll

`GET /v1/assets/{assetId}?installId=install-123456`

The Uploads workflow and upload resume path use this endpoint for upload state, proxy readiness, and post-upload artifact availability.

## Cancel Upload

`POST /v1/uploads/{assetId}/cancel`

Request:

```json
{"installId": "install-123456", "reason": "user_cancelled"}
```

The response is the canonical `AssetRecord`. Ready assets cannot be cancelled; cancelled uploads cannot be completed.

When a pending iOS background-upload manifest has an `assetId`, local cancellation is best-effort paired with this endpoint before the manifest is cleared. The app still clears local URLSession/chunk state if the server cancel report is unavailable, but proof metadata records whether the backend cancel was reported.

## Team Scan From Asset

`POST /v1/assets/{assetId}/team-scan`

Request:

```json
{
  "installId": "install-123456"
}
```

If the asset is not `proxy_ready`, the API returns `409 asset_not_ready`. When accepted, the response keeps the existing team-scan shape so current team-selection UI can continue to route through detected jersey options.

## Start AI From Asset

`POST /v1/assets/{assetId}/analysis-jobs`

Request:

```json
{
  "installId": "install-123456",
  "appVersion": "1.0",
  "analysisVersion": "cloud-v1",
  "teamSelection": {"mode": "all"}
}
```

If the asset is not `proxy_ready`, the API returns `409 asset_not_ready`. When accepted, the response includes `jobId`, `assetId`, proxy `storageKey`, `status`, `pollAfterSeconds`, quota fields, and `analysisMode`.

## Provider Dispatch Inputs

Inference, team-scan, and edit-planning payloads prefer `assetId` plus `storageKey`/`sourceObjectKey` when available. `sourceUrl` remains accepted only as a migration fallback and signed-read compatibility path for providers that do not yet share object storage credentials. The local backend and editing service materialize object keys first, then fall back to signed URLs.

For asset uploads, `storageKey` should be the proxy key after post-upload processing when `artifacts.proxyStorageKey` is available. The iOS client maps this as `analysisStorageKey` and does not start team scan, analysis, or edit handoff before the asset reports `proxy_ready` or `ready`.

## Upload Queue Projection

`UploadQueueProjection` in `WorkflowState.swift` is UI display state only. It maps current asset/job state into Uploads rows while preserving:

- `assetId`
- `storageKey`
- `proxyKey`
- upload asset status
- byte progress
- checksum and integrity status
- retry count and latest retryable error
- optional analysis job ID
- render attachment count
- clip count
- failure reason
- current import/upload/analysis status text
- resumable upload manifest summary
- cloud edit source object key

Do not persist `UploadQueueProjection` or treat it as a backend contract. If a future multi-item upload queue lands, feed its canonical DTOs through `UploadAssetQueueContract` and keep the same `UploadQueueItem` UI surface until the SwiftUI views intentionally change.

## Clip Accuracy Review

Canonical review feedback tags are:

- `duplicate`
- `wrong_team`
- `bad_window`
- `wrong_label`
- `low_quality`

These tags must persist from iOS review edits through backend edit DTOs, Worker admin clip review updates, and evaluation fixtures.

Benchmark metrics use stable camel-case names:

- `recallAtK`
- `precisionAtK`
- `boundaryErrorSeconds`
- `duplicateRate`

## AI Edit Handoff

AI Edit is a primary workflow section, but cloud ownership is unchanged. `CreateCloudEditJobRequest` sends additive `assetId` and `sourceClipIds` fields when available while preserving the backend-compatible `sourceObjectKey` plus full `clips` payload. `CreateCloudEditJobRequest.assetJobContract(assetId:)` exposes that asset-first shape for integration checks.

Review boundary nudges and feedback tags only mutate clip metadata that is already sent through existing clip/review payloads. They do not create local edit plans, local renders, or a new backend payload family.

`CreateCloudEditJobRequest` also sends additive `editIntent` and `idempotencyKey` fields. `sourceClipIds`, when present, must reference IDs included in the full `clips` compatibility payload.

## Structured Edit Intent

`editIntent.schemaVersion` is `edit-intent-v1`.

Required intent fields:

- `style`: `personal_highlight`, `full_game_highlight`, `coach_review`, `recruiting_reel`, `cinematic_mixtape`, `nba_recap`, `team_highlight`, `defense_focus`, or `custom`
- `pace`: `fast`, `balanced`, `cinematic`, `coach_review`, or `deliberate`
- `audioPreference`: `music_forward`, `game_audio`, `balanced`, or `muted`
- `chronology`: `best_first`, `chronological`, `story_arc`, or `coach_review`
- `captionDensity`: `minimal`, `clean`, `medium`, or `high`
- `hardConstraints`: `requireVisibleOutcome`, `requireFullPlayContext`, `rejectDuplicates`, `rejectDeadBall`, `defenseOnly`, `selectedTeamOnly`, and `maxCaptionCharacters`

Existing prompt UI maps into this schema on iOS. Backend clients that omit `editIntent` still get a server-derived schema from legacy prompt/template defaults, preserving the validated `EditPlan` flow.

## Edit Job Durability

Edit job payloads and plans persist to render storage under the existing durable editing namespace. Edit creation idempotency keys are indexed in the durable store, so retrying a create request after service reload returns the original edit job when the install owner matches.

Render jobs continue to use the existing durable render state store, leases, indexes, and render idempotency flow.

## Worker Compatibility

The Cloudflare Worker includes additive `assetId` fields in create/poll responses and additive `assetId/storageKey` fields in internal team-scan and inference dispatch payloads. For the existing R2 flow, `assetId` maps to `jobId` and internal `storageKey` maps to `sourceObjectKey`.

Public Worker responses keep `storageKey` null/redacted to preserve object-key redaction guarantees. Providers may continue reading `sourceUrl` during migration, but new inference/editing code should prefer `assetId` plus internal `storageKey` when present.

## Legacy Manual URL Compatibility

Internal inference endpoints still accept `sourceUrl` when `assetId`, `storageKey`, and `sourceObjectKey` are absent. This is compatibility-only and should not be the normal app path.

## Cloud-First Boundary

iOS remains the control surface:

- import/upload
- queue and job status
- review decisions and clip boundary metadata
- style, duration, aspect ratio, and prompt selection
- cloud edit-plan/render job requests
- downloaded MP4 preview/save/share/open-in

iOS must not add local production analysis, AI edit planning, final rendering, renderer command generation, or fake cloud job state.
