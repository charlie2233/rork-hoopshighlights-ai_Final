# Upload Pipeline Integration TODO

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
- [ ] Keep the existing manual URL input behind compatibility/debug UI only.

## Detection/Edit Agents

- [ ] Prefer `assetId` and `storageKey` in inference/team-scan/edit request payloads.
- [ ] Treat `sourceUrl` as legacy fallback only.
- [ ] Consume `proxyStorageKey` for first-preview/edit planning when available.
- [ ] Do not start expensive analysis/edit planning before `proxy_ready`.

## Verification

- [x] Add backend unit tests for init contract, multipart completion, status transitions, and proxy-ready gating.
- [x] Add upload benchmark script reporting time-to-first-preview, full upload time, and retry/resume success.
- [x] Add Swift contract decode tests once UI models land.
- [ ] Add managed object-storage smoke after Worker/provider deployment is available.
