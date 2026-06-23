# HoopsClips UI Workflow Contract

This branch exposes the iOS app as four production workflow sections:

1. Uploads
2. Review
3. AI Edit
4. Exports

## Canonical Inputs

The UI consumes existing contracts instead of inventing local payloads:

- Upload and analysis job state: `ios/HoopsClips/HoopsClips/Models/CloudAnalysisTypes.swift`
- Clip review state: `ios/HoopsClips/HoopsClips/Models/Clip.swift`
- AI Edit request, plan, render, history, and download state: `ios/HoopsClips/HoopsClips/Models/CloudEditTypes.swift`
- Editing backend plan and render ownership: `ios/backend/app/editing.py`
- Durable render job status: `services/editing/editing_app/models.py`

The upload-agent contract is asset-first. The queue projection accepts `assetId`, `storageKey`, `proxyKey`, `status`, byte progress, optional `analysisJobId`, clip count, and failure reason. It follows the upload lifecycle:

1. `initialized`
2. `uploading`
3. `uploaded`
4. `processing`
5. `proxy_ready`
6. `ready` or `failed`

AI analysis, team scan, and edit planning remain blocked until an asset reaches `proxy_ready` or `ready`.

## UI Projections

`UploadQueueProjection` in `WorkflowState.swift` is the only new UI projection. It maps the current asset/job state into display rows while preserving:

- `assetId`
- `storageKey`
- `proxyKey`
- upload asset status
- `cloudAnalysisJobID`
- `cloudEditSourceObjectKey`
- current import/upload/analysis status text
- resumable upload manifest summary
- clip count

This is display state only. It is not a new backend contract.

`CreateCloudEditJobRequest` now sends additive `assetId` and `sourceClipIds` fields when available while preserving the current backend-compatible `sourceObjectKey` plus full `clips` payload. `CreateCloudEditJobRequest.assetJobContract(assetId:)` exposes that asset-first shape for integration checks.

## Cloud-First Boundary

iOS remains the control surface:

- import/upload
- queue and job status
- review decisions and clip boundary metadata
- style, duration, aspect-ratio, and prompt selection
- cloud edit-plan/render job requests
- downloaded MP4 preview/save/share

iOS must not add local production analysis, AI edit planning, or final rendering.
