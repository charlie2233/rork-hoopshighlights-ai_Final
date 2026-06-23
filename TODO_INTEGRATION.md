# Workflow-First Integration TODO

## Backend Agent

- [x] Add local asset upload init/complete APIs.
- [x] Add local disk and object-storage-compatible upload adapter interfaces.
- [x] Add local multipart assemble path.
- [x] Add `proxy_ready` asset status and FFmpeg-backed proxy/thumbnail/waveform post-upload artifacts with safe local fallback.
- [x] Add asset-based analysis start gate.
- [x] Add asset-based team scan gate for detected-team preselection.
- [x] Keep legacy manual URL fallback for internal inference.
- [ ] Replace inline local post-upload processing with the durable managed queue.
- [ ] Add durable post-upload queue for managed mode instead of inline local processing.

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
- [x] Keep Exports focused on rendered/downloaded MP4 states and read latest status from `HighlightsViewModel.latestCloudEditRenderStatus`.
- [ ] Keep the existing manual URL input behind compatibility/debug UI only.

## Detection/Edit Agents

- [ ] Prefer `assetId` and `storageKey` in inference/team-scan/edit request payloads.
- [ ] Treat `sourceUrl` as legacy fallback only.
- [ ] Consume `proxyStorageKey` for first-preview/edit planning when available.
- [ ] Do not start expensive analysis/edit planning before `proxy_ready`.
- [x] Confirm AI Edit tab still calls cloud edit plan and render endpoints through `CloudEditService`; `assetId` and `sourceClipIds` are additive live fields and `sourceObjectKey` plus full `clips` remain the compatibility route.
- [x] Confirm boundary nudges remain metadata-only and are reflected in cloud edit candidate clips through `CreateCloudEditJobRequest.clips`.

## Verification

- [x] Add backend unit tests for init contract, multipart completion, status transitions, and proxy-ready gating.
- [x] Add upload benchmark script reporting time-to-first-preview, full upload time, and retry/resume success.
- [x] Add Swift contract decode tests once UI models land.
- [x] Add workflow projection unit tests.
- [x] Add workflow UI smoke coverage for Uploads -> Review -> AI Edit -> Exports navigation.
- [ ] Re-run `HoopsClipsTests` after this integration branch resolves conflicts.
- [ ] Re-run the workflow UI smoke after this integration branch resolves conflicts.
- [ ] Add managed object-storage smoke after Worker/provider deployment is available.
