# Workflow-First Integration TODO

## Backend Agent

- [x] Add local asset upload init/complete APIs.
- [x] Add local disk and object-storage-compatible upload adapter interfaces.
- [x] Add local multipart assemble path.
- [x] Add `proxy_ready` asset status and FFmpeg-backed proxy/thumbnail/waveform post-upload artifacts with safe local fallback.
- [x] Add asset-based analysis start gate.
- [x] Add asset-based team scan gate for detected-team preselection.
- [x] Keep legacy manual URL fallback for internal inference.
- [x] Add canonical `AssetRecord`/asset DTO compatibility names across backend, iOS, and Worker surfaces.
- [x] Replace inline local post-upload processing with the durable managed queue.
- [x] Add durable post-upload queue for managed mode instead of inline local processing.

## Detection Agent

- [x] Add staged detection pipeline contracts for proposal, embedding rerank, classifier, merge, and taxonomy.
- [x] Add `/v2/detection/analyze` as an internal validation route.
- [x] Add `candidateClips`, `rankScore`, stage scores, top labels, raw labels, canonical label fields, and provenance metadata.
- [x] Preserve `/v1/analysis/jobs`, `/v1/analysis/jobs/{jobId}/start`, and `/v1/analysis/jobs/{jobId}` compatibility.
- [x] Preserve `/api/ai/analyze` and `/api/ai/result/{jobId}` legacy Worker aliases.
- [x] Add detection taxonomy data and model registry docs.
- [x] Add deterministic benchmark CLI for the detection pipeline.
- [x] Add real OpenCLIP/SigLIP runtime adapters behind `EmbeddingAdapter` without changing response shapes.
- [x] Add real R2Plus1D model loading behind `VideoClassifierAdapter` without changing response shapes.

## UI Agent

- [x] Introduce `AssetUploadInitResponse`, `AssetStatusResponse`, and `AssetAnalysisJobResponse` Swift models.
- [x] Migrate upload manifest identity from `jobId` to `assetId` while preserving a compatibility bridge for old manifests.
- [x] After upload completion, poll `/v1/assets/{assetId}` until `proxy_ready` before team scan/start.
- [x] Show an honest `processing uploaded video` or `preparing first preview` state between upload completion and AI start.
- [x] Redact `storageKey`, `sourceObjectKey`, signed URLs, and full paths in proof/status copy.
- [x] Keep `UploadQueueProjection` as a view projection over canonical job state; do not persist it.
- [x] Promote AI Edit into its own primary workflow tab while keeping History and Settings secondary.
- [x] Keep Review actions wired to `Clip.isKept`: Keep, Nah, Keep Strong, Skip Weak, team filters, feedback tags, and boundary nudges.
- [x] Keep Review shortcut routing: `K` keep, `D` discard, `N` Nah compatibility, `1`-`5` feedback tags, `[`/`]` boundary nudges.
- [x] Persist the five canonical review feedback tags: `duplicate`, `wrong_team`, `bad_window`, `wrong_label`, `low_quality`.
- [x] Read detection output as `results.candidateClips ?? results.clips` where detection v2 metadata is available.
- [x] Keep Exports focused on rendered/downloaded MP4 states and read latest status from `HighlightsViewModel.latestCloudEditRenderStatus`.
- [x] Keep the existing manual URL input behind compatibility/debug UI only.

## Detection/Edit Agents

- [x] Prefer `assetId` and `storageKey` in inference/team-scan/detection/edit request payloads.
- [x] Treat `sourceUrl` as legacy fallback only.
- [x] Consume `proxyStorageKey` for first-preview/edit planning when available.
- [x] Do not start expensive analysis/edit planning before `proxy_ready`.
- [x] Confirm AI Edit tab still calls cloud edit plan and render endpoints through `CloudEditService`; `assetId` and `sourceClipIds` are additive live fields and `sourceObjectKey` plus full `clips` remain the compatibility route.
- [x] Prefer `rankScore` and `scores.finalScore` for candidate ordering when present.
- [x] Preserve `teamAttributionStatus`, `nativeShotSignals`, and `shouldAutoKeep` gates.
- [x] Send structured `editIntent` with style, pace, audio preference, chronology, caption density, and hard constraints.
- [x] Send an edit-job `idempotencyKey` and preserve replay-safe edit creation in backend/service storage.
- [x] Echo `assetId`, `sourceObjectKey`, `sourceClipIds`, `editIntent`, candidate clip count, and full candidate clips on edit-job responses.
- [x] Confirm boundary nudges remain metadata-only and are reflected in cloud edit candidate clips through `CreateCloudEditJobRequest.clips`.
- [x] Reset AI Edit/render state when source asset identity or candidate clips change.

## Verification

- [x] Add backend unit tests for init contract, multipart completion, status transitions, and proxy-ready gating.
- [x] Add upload benchmark script reporting time-to-first-preview, full upload time, and retry/resume success.
- [x] Add clip-accuracy calibration fixtures and evaluation metrics: `recallAtK`, `precisionAtK`, `boundaryErrorSeconds`, and `duplicateRate`.
- [x] Add Swift contract decode tests once UI models land.
- [x] Add workflow projection unit tests.
- [x] Add workflow UI smoke coverage for Uploads -> Review -> AI Edit -> Exports navigation.
- [x] Add edit request encoding coverage for `assetId`, `sourceClipIds`, `editIntent`, and `idempotencyKey`.
- [x] Add backend/service idempotency replay coverage for edit-job creation.
- [x] Add detection v2 route and pipeline unit tests.
- [x] Add editing service tests for Worker dispatch and detection v2 candidate output.
- [x] Re-run backend py_compile after detection merge.
- [x] Re-run upload and detection backend tests after detection merge.
- [x] Re-run editing service tests after detection merge.
- [x] Re-run detection benchmark CLI after detection merge.
- [x] Re-run Worker typecheck and tests after detection merge.
- [x] Re-run focused iOS AI Edit state reset test after detection merge.
- [x] Re-run workflow UI smoke after final workflow/upload/detection/edit integration.
- [x] Re-run full `HoopsClipsTests` suite if a full-suite Xcode long-tail pass is required before PR merge.
- [x] Add managed object-storage smoke script for provider-backed upload adapter proof.
- [ ] Run managed object-storage smoke after Worker/provider deployment credentials are available.
