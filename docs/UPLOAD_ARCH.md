# Upload Architecture

HoopClips now has an asset-first upload path for scalable video intake.

## Flow

1. Client calls `POST /v1/uploads/init`.
2. Backend creates an asset record and returns either one signed PUT target or the full multipart plan, including every signed part target.
3. Client uploads directly to Cloudflare R2. Multipart uploads can transfer up to six parts concurrently on an unconstrained network.
4. Client calls `POST /v1/uploads/{assetId}/complete`.
5. The Worker verifies or assembles the R2 source object. Backends with an artifact-processing lane can then run:
   - proxy MP4 generation
   - thumbnail generation
   - waveform metadata generation
6. Client polls `GET /v1/assets/{assetId}`.
7. Client can scan teams with `POST /v1/assets/{assetId}/team-scan` once the source is ready.
8. Client starts AI with `POST /v1/assets/{assetId}/analysis-jobs` once the source is ready.

The Cloudflare Worker asset route is a compatibility bridge over the existing job state, queue, and R2 objects. It returns the owner-scoped source `storageKey` required by the current iOS asset decoder while the legacy public job-poll response continues to redact storage keys. The Worker currently marks a verified source as `ready` with empty optional proxy, thumbnail, and waveform artifacts; iOS therefore uses the source object until a separate proxy artifact exists.

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

The Swift client attempts the asset upload path first:

`uploads/init -> signed upload -> uploads/{assetId}/complete -> assets/{assetId} proxy_ready -> team-scan or analysis-jobs`

The Worker implements that complete route set. The client still falls back to `analysis/jobs -> uploadUrl -> start` when an older deployment returns an unavailable-route response, which keeps existing builds compatible during rollout. New resume manifests persist optional `assetId`, `storageKey`, and asset multipart targets so foreground-interrupted asset uploads complete through the asset API instead of the legacy job-start route.

## Upload Throughput Policy

Large uploads use adaptive multipart sizing in both the Worker and the asset-first client contract. The planner uses 8–32 MiB parts and targets about 24 parts per upload. A 380 MiB basketball video therefore uses 24 parts at 16 MiB instead of 48 parts at 8 MiB, cutting signing, background-session, and chunk-staging overhead without changing the uploaded bytes. The canonical init response signs all part targets concurrently and returns them together, so the client does not need a control-plane request before each part.

Before upload, the iOS control surface automatically prepares a balanced 720p analysis source for recordings that are at least 12 minutes or 256 MiB. Shorter, smaller sources keep their original bytes, and an optimized export is used only when it saves at least 18 percent. Fast Upload Mode can still request the compact profile. This changes transfer size only: detection, edit planning, and rendering remain cloud-owned.

The iOS client runs up to six multipart lanes on a normal network. Expensive networks remain capped at two lanes, and Low Data Mode remains capped at one. Before launching the first multipart wave, it waits up to 300 ms for iOS to classify the network; if classification is still pending it safely starts with one lane. It rechecks the cap between completed parts so Wi-Fi/cellular changes affect the remaining upload. Upload sessions explicitly allow six per-host connections, and active upload tasks use high priority while the user is waiting.

All parts for one multipart video now run as separate upload tasks inside one shared background `URLSession`. This follows Apple's small-session guidance, lets iOS schedule parallel transfers together, and avoids creating and invalidating a background session for every chunk. Each task carries a persisted `part-N.try-M` description so relaunch handling can map a completed task back to its manifest part. The session identifier is scoped to the upload ID, preventing a late callback from an older upload from writing an ETag into a replacement manifest. Legacy per-part session identifiers remain readable for uploads created by older builds.

Each lane keeps bounded chunk memory, persists completed parts, removes its uniquely named atomic staging file after every terminal attempt, and retries idle transfers inside the signed-upload window. If the coordinating Swift task is canceled, its continuation detaches promptly while the file-backed background transfer finishes and persists a successful ETag through the same resume path. The shared session remains recorded in the resume manifest until every part completes, preserving app suspension and relaunch recovery.

## Status Semantics

- `initialized`: upload target exists, client has not uploaded yet.
- `uploading`: multipart parts are arriving.
- `uploaded`: source object exists, post-upload processing has not completed.
- `processing`: proxy/thumbnail/waveform generation is running.
- `proxy_ready`: AI and first preview may start.
- `ready`: reserved for final asset readiness after richer artifact generation.
- `failed`: upload or post-upload processing failed.

## Cloud-First Rule

iOS remains the control surface. Upload, proxy generation, thumbnail/waveform extraction, AI analysis, edit planning, and render production stay backend-owned.
