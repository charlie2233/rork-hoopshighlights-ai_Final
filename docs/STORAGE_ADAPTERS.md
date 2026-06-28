# Storage Adapters

The upload pipeline uses `UploadStorageAdapter` in `ios/backend/app/upload_storage.py`.

## Local Disk Adapter

Class: `LocalDiskUploadStorageAdapter`

Use for simulator and local backend development.

Environment:

```bash
export HOOPS_ENVIRONMENT=local
export HOOPS_UPLOAD_STORAGE_PROVIDER=local
export HOOPS_UPLOAD_ROOT=/tmp/hoops-ai
```

Behavior:

- Returns local PUT URLs under `/v1/internal/assets/...`.
- Stores source/proxy/artifact objects under `HOOPS_UPLOAD_ROOT`.
- Supports local multipart by storing part files under `multipart/{assetId}` and assembling them on complete.
- Does not expose public file URLs.

## Object Storage Compatible Adapter

Class: `ObjectStorageCompatibleUploadStorageAdapter`

Use for R2/S3-compatible signed URLs and multipart uploads.

Environment:

```bash
export HOOPS_UPLOAD_STORAGE_PROVIDER=object
export HOOPS_OBJECT_STORAGE_BUCKET=...
export HOOPS_OBJECT_STORAGE_ENDPOINT_URL=...
export HOOPS_OBJECT_STORAGE_ACCESS_KEY_ID=...
export HOOPS_OBJECT_STORAGE_SECRET_ACCESS_KEY=...
export HOOPS_OBJECT_STORAGE_REGION=auto
```

Existing R2 env names are also accepted as a fallback:

```bash
export HOOPS_R2_BUCKET=...
export HOOPS_R2_ENDPOINT_URL=...
export HOOPS_R2_ACCESS_KEY_ID=...
export HOOPS_R2_SECRET_ACCESS_KEY=...
export HOOPS_R2_REGION=auto
```

Behavior:

- Returns signed single PUT URLs.
- Creates S3-compatible multipart upload IDs and signed part URLs.
- Completes multipart uploads with caller-provided ETags.
- Materializes storage keys to local temp files for backend analysis.
- Writes proxy/thumbnail/waveform artifacts back to object storage.

## Contract Rules

- Storage keys are private implementation details. Do not print full keys in app proof logs, Formspree reports, or user-visible errors.
- Signed URLs are bearer tokens. Do not store or relay them beyond the active upload operation.
- `assetId` is the UI-safe identifier for status polling and retry/resume state.
- `storageKey` is for backend/provider handoff only.
