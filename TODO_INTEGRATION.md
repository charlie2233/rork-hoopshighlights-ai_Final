# Multimodal Rerank Integration TODO

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
- [x] Preserve asset/source identity through Detection V2 rerank evidence: `assetId`, `storageKey`, `sourceObjectKey`, `uploadTraceId`, `inferenceAttemptId`, and `jobId`.

## Detection Agent

- [x] Add staged Detection V2 pipeline route and compatibility aliases.
- [x] Add basketball taxonomy data file and mapper.
- [x] Add Detection V2 tests and benchmark CLI scaffold.
- [x] Add first-class embedding/rerank provider interface with batching/cache hooks and kill switch.
- [x] Add basketball prompt/taxonomy support for event type, outcome, crowd reaction, team identity, bad-window, duplicate, and wrong-team.
- [x] Persist rerank evidence/scores on candidate/output schemas.
- [x] Keep heuristic + HoopCut/autohighlight fallback when embedding rerank is disabled, unavailable, or times out.
- [x] Add eval harness metrics: precision, recall, F1, nDCG, MRR, Recall@K, precision@K, and error buckets.

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
- [x] Keep Exports focused on rendered/downloaded MP4 states and read latest status from `HighlightsViewModel.latestCloudEditRenderStatus`.
- [x] Keep the existing manual URL input behind compatibility/debug UI only.
- [x] Confirm Review reads `results.candidateClips ?? results.clips` after rerank schema additions.
- [x] Keep rerank provenance diagnostics-only unless explicitly promoted in product UI.

## Edit Agent

- [x] Prefer `assetId` and `storageKey` in inference/team-scan/edit request payloads.
- [x] Treat `sourceUrl` as legacy fallback only.
- [x] Consume `proxyStorageKey` for first-preview/edit planning when available.
- [x] Do not start expensive analysis/edit planning before `proxy_ready`.
- [x] Confirm AI Edit tab still calls cloud edit plan and render endpoints through `CloudEditService`; `assetId` and `sourceClipIds` are additive live fields and `sourceObjectKey` plus full `clips` remain the compatibility route.
- [x] Send structured `editIntent` with style, pace, audio preference, chronology, caption density, and hard constraints.
- [x] Send an edit-job `idempotencyKey` and preserve replay-safe edit creation in backend/service storage.
- [x] Echo `assetId`, `sourceObjectKey`, `sourceClipIds`, `editIntent`, candidate clip count, and full candidate clips on edit-job responses.
- [x] Confirm boundary nudges remain metadata-only and are reflected in cloud edit candidate clips through `CreateCloudEditJobRequest.clips`.
- [x] Prefer `rankScore` and `scores.finalScore` for candidate ordering when present while keeping existing team/native-shot/auto-keep gates.

## Verification

- [x] Add backend unit tests for init contract, multipart completion, status transitions, and proxy-ready gating.
- [x] Add upload benchmark script reporting time-to-first-preview, full upload time, and retry/resume success.
- [x] Add clip-accuracy calibration fixtures and evaluation metrics: `recallAtK`, `precisionAtK`, `boundaryErrorSeconds`, and `duplicateRate`.
- [x] Add Swift contract decode tests once UI models land.
- [x] Add workflow projection unit tests.
- [x] Add workflow UI smoke coverage for Uploads -> Review -> AI Edit -> Exports navigation.
- [x] Add edit request encoding coverage for `assetId`, `sourceClipIds`, `editIntent`, and `idempotencyKey`.
- [x] Add backend/service idempotency replay coverage for edit-job creation.
- [x] Re-run iOS build-for-testing after workflow integration conflicts resolve.
- [x] Re-run focused `HoopsClipsTests` integration lanes: `WorkflowStateTests`, edit request encoding, asset upload decode, and asset queue decode.
- [x] Re-run the workflow UI smoke after workflow integration conflicts resolve.
- [x] Run Python detection tests.
- [x] Run backend rerank/eval tests.
- [x] Run editing service tests.
- [x] Run control-plane typecheck/tests if Worker contracts changed.
- [x] Run `scripts/benchmark_detection_pipeline.py --json`.
- [ ] Re-run the full `HoopsClipsTests` suite if a full-suite Xcode long-tail pass is required before PR merge.
- [ ] Add managed object-storage smoke after Worker/provider deployment is available.
