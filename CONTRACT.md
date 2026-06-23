# HoopClips Upload Pipeline Contract

This branch introduces an asset-first upload contract while preserving the legacy `POST /v1/analysis/jobs` compatibility path.

## Asset Upload Lifecycle

Status order:

1. `initialized`
2. `uploading`
3. `uploaded`
4. `processing`
5. `proxy_ready`
6. `ready` or `failed`

AI analysis, team scan, and edit planning should not start until the asset is `proxy_ready` or `ready`.

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

Multipart response shape:

```json
{
  "assetId": "asset_...",
  "storageKey": "assets/asset_.../source/game.mp4",
  "status": "initialized",
  "uploadMode": "multipart",
  "multipart": {
    "uploadId": "local-asset_...",
    "partSizeBytes": 8388608,
    "partCount": 3,
    "parts": [
      {
        "partNumber": 1,
        "uploadUrl": "http://127.0.0.1:8080/v1/internal/assets/asset_.../parts/1",
        "uploadMethod": "PUT",
        "uploadHeaders": {"Content-Type": "video/mp4"}
      }
    ]
  },
  "expiresAt": "2026-06-23T08:00:00Z",
  "pollAfterSeconds": 1,
  "uploadState": "waiting_for_client_upload"
}
```

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
  "status": "proxy_ready",
  "artifacts": {
    "proxyStorageKey": "assets/asset_.../proxy/proxy.mp4",
    "thumbnailStorageKeys": ["assets/asset_.../thumbnails/preview_0001.jpg"],
    "waveformStorageKey": "assets/asset_.../metadata/waveform.json"
  },
  "pollAfterSeconds": 1
}
```

## Asset Poll

`GET /v1/assets/{assetId}?installId=install-123456`

UI should use this endpoint for upload state, proxy readiness, and post-upload artifact availability.

## Team Scan From Asset

`POST /v1/assets/{assetId}/team-scan`

Request:

```json
{
  "installId": "install-123456"
}
```

If the asset is not `proxy_ready`, the API returns `409 asset_not_ready`. When accepted, the response keeps the existing team-scan shape so the current team-selection UI can continue to route through detected jersey options:

```json
{
  "jobId": "asset_...",
  "status": "scanned",
  "detectedTeams": [
    {
      "teamId": "team_dark",
      "label": "Dark jerseys",
      "colorLabel": "black",
      "primaryColorHex": "#111111",
      "confidence": 0.91,
      "source": "quick_scan"
    }
  ]
}
```

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

If the asset is not `proxy_ready`, the API returns `409 asset_not_ready`. When accepted, the response includes:

```json
{
  "jobId": "job...",
  "assetId": "asset_...",
  "storageKey": "assets/asset_.../proxy/proxy.mp4",
  "status": "queued",
  "pollAfterSeconds": 1,
  "quotaRemainingToday": 2,
  "analysisMode": "cloud"
}
```

## Worker Compatibility

The Cloudflare Worker now includes additive `assetId` fields in create/poll responses and additive `assetId/storageKey` fields in internal team-scan and inference dispatch payloads. For the existing R2 flow, `assetId` maps to `jobId` and internal `storageKey` maps to `sourceObjectKey`.

Public Worker responses keep `storageKey` null/redacted to preserve existing object-key redaction guarantees. Providers may continue reading `sourceUrl` during migration, but new editing/inference code should prefer `assetId` plus internal `storageKey` when the field is present.

## Legacy Manual URL Compatibility

Internal inference endpoints still accept `sourceUrl` when `assetId`, `storageKey`, and `sourceObjectKey` are absent. This is compatibility-only and should not be the normal app path.
