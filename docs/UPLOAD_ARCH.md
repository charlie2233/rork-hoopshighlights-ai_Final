# Upload Architecture

HoopClips now has an asset-first upload path for scalable video intake.

## Flow

1. Client calls `POST /v1/uploads/init`.
2. Backend creates an asset record and returns a single PUT or multipart upload plan.
3. Client uploads directly to the returned target.
4. Client calls `POST /v1/uploads/{assetId}/complete`.
5. Backend runs post-upload processing:
   - proxy MP4 generation
   - thumbnail generation
   - waveform metadata generation
6. Client polls `GET /v1/assets/{assetId}`.
7. Client can scan teams with `POST /v1/assets/{assetId}/team-scan` only after `proxy_ready`.
8. Client starts AI with `POST /v1/assets/{assetId}/analysis-jobs` only after `proxy_ready`.

## Local Implementation

The local FastAPI backend stores assets under `HOOPS_UPLOAD_ROOT`:

- source: `assets/{assetId}/source/{filename}`
- proxy: `assets/{assetId}/proxy/proxy.mp4`
- thumbnail: `assets/{assetId}/thumbnails/preview_0001.jpg`
- waveform: `assets/{assetId}/metadata/waveform.json`

The current local post-upload job attempts FFmpeg/ffprobe proxy and thumbnail generation, writes waveform metadata, and falls back to a source copy plus placeholder thumbnail when local test bytes are not valid video. That keeps the lifecycle testable while preserving the backend-owned processing boundary. Managed mode should run the same work on a durable queue before public cutover.

## AI Boundary

AI jobs consume asset identity and storage keys:

- `assetId` identifies the user-uploaded asset.
- `storageKey` identifies the object AI should read.
- `proxyStorageKey` is preferred once available.

Legacy internal `sourceUrl` is still accepted as a compatibility path, but normal clients should not depend on public pasted video URLs.

## iOS Client Behavior

The Swift client now attempts the asset upload path first:

`uploads/init -> signed upload -> uploads/{assetId}/complete -> assets/{assetId} proxy_ready -> team-scan or analysis-jobs`

If `/v1/uploads/init` is not available, the client falls back to the legacy `analysis/jobs -> uploadUrl -> start` path for current Worker compatibility. New resume manifests persist optional `assetId`, `storageKey`, and asset multipart targets so foreground-interrupted asset uploads complete through the asset API instead of the legacy job-start route.

The client also persists structured upload capabilities from `/v1/analysis/capabilities`. `maxConcurrentPartUploads` caps multipart lanes, while iOS network policy can still reduce lanes for constrained or expensive networks. Pending asset-upload cancellation calls `/v1/uploads/{assetId}/cancel` best-effort before local resume state is cleared.

## Status Semantics

- `initialized`: upload target exists, client has not uploaded yet.
- `uploading`: multipart parts are arriving.
- `uploaded`: source object exists, post-upload processing has not completed.
- `processing`: proxy/thumbnail/waveform generation is running.
- `proxy_ready`: AI and first preview may start.
- `ready`: reserved for final asset readiness after richer artifact generation.
- `failed`: upload or post-upload processing failed.
- `cancelled`: user or client cancellation was recorded; complete/start calls must not proceed.

## Managed Smoke

Use the privacy-safe managed smoke harness for provider or Worker deployments:

```bash
python3 scripts/managed_asset_upload_smoke.py \
  --base-url "$HOOPS_MANAGED_ASSET_UPLOAD_BASE_URL" \
  --upload-preference multipart \
  --part-size-bytes 4194304 \
  --expect-multipart \
  --evidence-path artifacts/managed_asset_upload_smoke.json
```

The JSON output hashes `assetId`, object keys, URLs, and local paths. A passing run proves multipart upload, duplicate-safe completion, checksum/integrity reporting when available, and `proxy_ready` polling. Use `--allow-processing` only when debugging queue handoff; release proof should keep the default proxy-ready requirement.

## Cloud-First Rule

iOS remains the control surface. Upload, proxy generation, thumbnail/waveform extraction, AI analysis, edit planning, and render production stay backend-owned.
