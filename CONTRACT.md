# HoopClips Workflow, Upload, And Detection Contract

This integration branch combines the asset-first upload pipeline, Agent A's accuracy foundations, Agent B's AI Edit engine contracts, the workflow-first iOS shell, and Detection V2. It keeps backend/client contracts canonical and treats UI state as projections over those contracts, not as forked payloads.

## Cloud Ownership

HoopClips analysis, multimodal reranking, edit planning, and rendering remain cloud-backend owned. The iOS app is the control surface for upload, review, AI Edit requests, job status, previews, downloads, share sheets, and external editor handoff.

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
- Local backend asset and detection routes: `ios/backend/app/api.py`
- Editing backend plan and render ownership: `ios/backend/app/editing.py`
- Worker additive asset and candidate fields: `services/control-plane/src/types.ts`
- Durable render job status: `services/editing/editing_app/models.py`

## Asset Upload Lifecycle

The upload-agent contract is asset-first. Upload, team scan, cloud analysis, and edit planning should not start expensive backend work until an asset reaches `proxy_ready` or `ready`.

Status order:

1. `initialized`
2. `uploading`
3. `uploaded`
4. `processing`
5. `proxy_ready`
6. `ready` or `failed`

Canonical asset state is represented by `AssetRecord`/`CloudAssetStatusResponse` and additive DTO fields named `assetId`, `storageKey`, and `proxyStorageKey`. During migration, legacy job fields stay valid: `jobId`, `uploadUrl`, `sourceObjectKey`, `resultObjectKey`, `sourceUrl`, and `/v1/analysis/jobs/{jobId}/start` remain supported.

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

## Asset Routes

`POST /v1/uploads/init` creates a single-part or multipart upload target and returns `assetId`, `storageKey`, upload target details, expiration, polling hints, and `uploadState`.

`POST /v1/uploads/{assetId}/complete` records completion and moves the asset into `processing`, `proxy_ready`, or `failed` depending on local or managed post-upload processing.

`GET /v1/assets/{assetId}?installId=...` is the Uploads workflow and resume endpoint for upload state, proxy readiness, and post-upload artifact availability.

`POST /v1/assets/{assetId}/team-scan` and `POST /v1/assets/{assetId}/analysis-jobs` require `proxy_ready` or `ready`; otherwise they return `409 asset_not_ready`.

## Provider Dispatch Inputs

Inference, team-scan, detection, and edit-planning payloads prefer `assetId` plus `storageKey`/`sourceObjectKey` when available. `sourceUrl` remains accepted only as a migration fallback and signed-read compatibility path for providers that do not yet share object storage credentials.

For asset uploads, `storageKey` should be the proxy key after post-upload processing when `artifacts.proxyStorageKey` is available. The iOS client maps this as `analysisStorageKey` and does not start team scan, analysis, or edit handoff before the asset reports `proxy_ready` or `ready`.

## Detection V2 Pipeline

Detection is staged and cloud-backend owned:

1. `proposal`: audio/visual windows or provider candidates identify likely event windows.
2. `embedding_rerank`: CLIP/SigLIP-style semantic adapters rerank proposals against basketball product labels.
3. `classifier`: baseline video classifier emits raw event labels and top-label scores.
4. `merge`: overlapping candidates are merged into final reviewable clip candidates.
5. `taxonomy`: raw labels map to product labels and canonical metadata.

The public mobile upload path can continue through `/v1/analysis/*`; `POST /v2/detection/analyze` is the first-class backend detection route and internal validation path. Legacy aliases such as `/api/ai/analyze` and `/api/ai/result/{jobId}` remain compatibility routes.

## Detection Request Identity

Detection and rerank requests preserve source identity and trace fields when present:

- `jobId`
- `requestId`
- `traceId`
- `uploadTraceId`
- `inferenceAttemptId`
- `installId`
- `assetId`
- `storageKey`
- `sourceObjectKey`
- `sourceUrl`
- `filename`
- `contentType`
- `durationSeconds`
- `appVersion`
- `analysisVersion`
- `schemaVersion`
- `modelVersion`

## Candidate Clip Schema

Analysis responses preserve `clips` for legacy clients and may add `candidateClips` for Detection V2. New clients should read `results.candidateClips ?? results.clips`.

Candidate fields are additive and must remain safe for iOS, Worker, and edit-engine consumers:

- `id` / `clipId`
- `startTime`
- `endTime`
- `duration`
- `label`
- `canonicalLabel`
- `eventFamily`
- `outcome`
- `crowdReaction`
- `teamIdentity`
- `teamAttributionStatus`
- `nativeShotSignals`
- `shouldAutoKeep`
- `rankScore`
- `confidence`
- `sourceObjectKey` or redacted source identity for backend/internal use
- `scores.proposalScore`
- `scores.embeddingScore`
- `scores.classifierScore`
- `scores.mergeScore`
- `scores.finalScore`
- `rerankEvidence`
- `provenance`
- `reviewTags`

Candidate clips may contain diagnostic provenance in backend responses. UI surfaces must not display raw signed URLs, provider secrets, object keys, or full filesystem paths. Review/product copy should prefer `label`, then `canonicalLabel`, `eventFamily`, and `outcome`.

## Rerank Evidence

Rerank evidence is diagnostic and additive. It should be useful to Review, AI Edit, and eval tooling without becoming a launch gate by itself.

Recommended shape:

```json
{
  "provider": "heuristic-embedding",
  "model": "clip-like-v0",
  "promptVersion": "basketball-taxonomy-v1",
  "killSwitch": false,
  "embeddingScore": 0.76,
  "textMatches": [
    {"label": "made three", "score": 0.76},
    {"label": "crowd reaction", "score": 0.62}
  ],
  "errorBuckets": ["boundary_ok"]
}
```

When the embedding provider is disabled, unavailable, or too slow, the pipeline falls back to heuristic + HoopCut/autohighlight behavior and records fallback provenance instead of changing response shape.

## Basketball Taxonomy

The backend taxonomy supports review and evaluation labels for:

- event type
- outcome
- crowd reaction
- team identity
- bad-window
- duplicate
- wrong-team

Canonical review feedback tags are:

- `duplicate`
- `wrong_team`
- `bad_window`
- `wrong_label`
- `low_quality`

These tags must persist from iOS review edits through backend edit DTOs, Worker admin clip review updates, and evaluation fixtures.

## Upload Queue Projection

`UploadQueueProjection` in `WorkflowState.swift` is UI display state only. It maps current asset/job state into Uploads rows while preserving:

- `assetId`
- `storageKey`
- `proxyKey`
- upload asset status
- byte progress
- optional analysis job ID
- clip count
- failure reason
- current import/upload/analysis status text
- resumable upload manifest summary
- cloud edit source object key

Do not persist `UploadQueueProjection` or treat it as a backend contract. If a future multi-item upload queue lands, feed its canonical DTOs through `UploadAssetQueueContract` and keep the same `UploadQueueItem` UI surface until the SwiftUI views intentionally change.

## AI Edit Ordering

AI Edit should use candidates that pass existing quality gates. Prefer `rankScore` and `scores.finalScore` when present, while preserving existing `teamAttributionStatus`, `nativeShotSignals`, `shouldAutoKeep`, source object, full `clips`, `assetId`, `sourceClipIds`, `editIntent`, and idempotency compatibility paths.

Boundary nudges remain metadata-only and are reflected in cloud edit candidate clips through `CreateCloudEditJobRequest.clips`; they do not create local renders or local edit plans.

## Accuracy Evaluation Metrics

Benchmark metrics use stable camel-case names:

- `precision`
- `recall`
- `f1`
- `ndcg`
- `mrr`
- `recallAtK`
- `precisionAtK`
- `boundaryErrorSeconds`
- `duplicateRate`

Error buckets should include at least `bad_window`, `duplicate`, `wrong_team`, `wrong_label`, `low_quality`, `missing_clip`, and `false_positive`.
