# HoopClips Workflow, Upload, Detection, And AI Edit Contract

This integration branch combines the asset-first upload pipeline, detection v2 accuracy foundations, AI Edit engine contracts, and the workflow-first iOS shell. Backend/client contracts remain canonical; iOS workflow state is a projection over those contracts, not a forked payload family.

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
- Workflow projection state: `ios/HoopsClips/HoopsClips/Models/WorkflowState.swift`
- Local backend asset routes and detection route wiring: `ios/backend/app/api.py`
- Detection pipeline and taxonomy: `ios/backend/app/detection_pipeline.py`, `ios/backend/app/taxonomy.py`, `ios/backend/app/model_registry.py`, and `ios/backend/app/data/basketball_taxonomy.json`
- Editing backend plan and render ownership: `ios/backend/app/editing.py` and `ios/backend/app/rendering.py`
- Worker additive asset and detection fields: `services/control-plane/src/types.ts` and `services/control-plane/src/routes/public.ts`
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

`POST /v1/uploads/init` accepts filename, content type, size, duration, install ID, app/analysis versions, upload preference, and optional multipart part size. The response includes `assetId`, source `storageKey`, upload mode, signed upload target, multipart metadata when needed, expiry, poll interval, and upload state.

`POST /v1/uploads/{assetId}/complete` records single-part or multipart completion, moves the asset into processing, and returns current asset artifacts. Managed runtimes enqueue post-upload proxy, thumbnail, and waveform generation through Cloud Tasks at `POST /v1/internal/assets/{assetId}/process`; local runtimes use the same dispatcher interface with an inline emulator.

`GET /v1/assets/{assetId}?installId=...` is the Uploads workflow and upload resume status endpoint. It is the source of truth for upload state, proxy readiness, and post-upload artifacts.

## Team Scan And Analysis From Asset

`POST /v1/assets/{assetId}/team-scan` accepts `installId`. If the asset is not `proxy_ready`, the API returns `409 asset_not_ready`. When accepted, the response keeps the existing team-scan shape for current team-selection UI.

`POST /v1/assets/{assetId}/analysis-jobs` accepts `installId`, app/analysis versions, and team selection. If the asset is not `proxy_ready`, the API returns `409 asset_not_ready`. When accepted, the response includes `jobId`, `assetId`, proxy `storageKey`, status, poll interval, quota fields, and `analysisMode`.

## Detection V2 Pipeline

Detection is staged and cloud-backend owned:

1. `proposal`: audio/visual windows or provider candidates identify likely event windows.
2. `embedding_rerank`: CLIP-like semantic adapter reranks proposals against basketball product labels.
3. `classifier`: baseline video classifier emits raw event labels and top-label scores.
4. `merge`: overlapping candidates are merged into final reviewable clip candidates.
5. `taxonomy`: research/raw labels map to product labels and canonical metadata.

`POST /v2/detection/analyze` is an internal backend validation route, not the mobile upload path. It accepts trace/job identifiers, install ID, source object key, optional signed source URL fallback, filename, content type, duration, app/analysis versions, schema version, and model version.

The response includes:

- `clipCount`
- `clips`
- `candidateClips`
- `diagnostics`
- `resultConfidence`
- `pipeline`
- `detectedTeams`
- `teamSelection`

Candidate clip items preserve the existing clip shape and add detection metadata when present:

- product fields: `label`, `canonicalLabel`, `eventFamily`, `eventSubtype`, `shotSubtype`, and `outcome`
- ordering fields: `rankScore`, `scores.finalScore`, and stage-specific score values
- model fields: `topLabels`, `rawTopLabels`, `pipelineStage`, and `pipelineVersion`
- provenance fields for proposal, embedding rerank, classifier, merge, and taxonomy

Old result readers can continue reading `results.clipCount`, `results.clips`, and `results.diagnostics`. New readers should prefer `results.candidateClips ?? results.clips`. UI copy should display product label fields in this order when present: `label`, `canonicalLabel`, `eventFamily`, `outcome`. Raw signed URLs, source object keys, provider secrets, and full storage paths must stay out of user-facing copy.

Missing inference/editing providers must fail queued jobs instead of returning synthetic stub AI. Embedding fallback is allowed only inside `provenance.embeddingRerank.status = "fallback"` and must set `pipeline.fallbackUsed = true` with a specific reason such as `embedding_adapter_unavailable`.

## Provider Dispatch Inputs

Inference, team-scan, detection, and edit-planning payloads prefer `assetId` plus `storageKey`/`sourceObjectKey` when available. `sourceUrl` remains accepted only as a migration fallback and signed-read compatibility path for providers that do not yet share object storage credentials. The local backend and editing service materialize object keys first, then fall back to signed URLs.

For asset uploads, `storageKey` should be the proxy key after post-upload processing when `artifacts.proxyStorageKey` is available. The iOS client maps this as `analysisStorageKey` and does not start team scan, analysis, or edit handoff before the asset reports `proxy_ready` or `ready`.

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

Do not persist `UploadQueueProjection` or treat it as a backend contract. If a future multi-item upload queue lands, feed canonical DTOs through `UploadAssetQueueContract` and keep the same `UploadQueueItem` UI surface until the SwiftUI views intentionally change.

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

AI Edit should use candidates that pass existing quality gates. It should prefer `rankScore` or `scores.finalScore` for candidate ordering when present while preserving `teamAttributionStatus`, `nativeShotSignals`, and `shouldAutoKeep` gates.

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

The Cloudflare Worker includes additive `assetId` fields in create/poll responses and additive `assetId/storageKey` fields in internal team-scan, inference, and detection dispatch payloads. For the existing R2 flow, `assetId` maps to `jobId` and internal `storageKey` maps to `sourceObjectKey`.

Existing clients remain supported:

- `POST /v1/analysis/jobs`
- `POST /v1/analysis/jobs/{jobId}/start`
- `GET /v1/analysis/jobs/{jobId}`
- `POST /v1/analyze`
- `POST /api/ai/analyze`
- `GET /api/ai/result/{jobId}`

Public Worker responses keep storage keys null/redacted to preserve object-key redaction guarantees. Providers may continue reading `sourceUrl` during migration, but new inference/editing code should prefer `assetId` plus internal `storageKey` when present.

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
