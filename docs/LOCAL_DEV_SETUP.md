# Local Upload Pipeline Setup

## Backend

```bash
cd /Users/hanfei/hc-agent-upload/ios/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export HOOPS_ENVIRONMENT=local
export HOOPS_PUBLIC_API_ENABLED=true
export HOOPS_ENABLE_LOCAL_UPLOAD_EMULATION=true
export HOOPS_UPLOAD_STORAGE_PROVIDER=local
export HOOPS_UPLOAD_ROOT=/tmp/hoops-ai-upload-pipeline

uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

## Single Upload Smoke

```bash
python scripts/upload_benchmark.py \
  --base-url http://127.0.0.1:8080 \
  --upload-preference single \
  --generated-size-bytes 1048576
```

Expected JSON fields:

- `timeToFirstPreviewSeconds`
- `fullUploadSeconds`
- `retryResumeSuccess`
- `finalAssetStatus: proxy_ready`
- `proxyStorageKey`

## Multipart/Resume Smoke

```bash
python scripts/upload_benchmark.py \
  --base-url http://127.0.0.1:8080 \
  --upload-preference multipart \
  --part-size-bytes 1048576 \
  --generated-size-bytes 3145728 \
  --retry-first-part
```

This re-uploads the first part before completion and reports `retryResumeSuccess`.

## Asset-First Managed Smoke Harness

The managed smoke harness uses the same public asset endpoints as provider deployments but keeps output shareable:

```bash
python3 scripts/managed_asset_upload_smoke.py \
  --base-url http://127.0.0.1:8080 \
  --generated-size-bytes 8388608 \
  --upload-preference multipart \
  --part-size-bytes 4194304 \
  --expect-multipart \
  --evidence-path /tmp/managed_asset_upload_smoke_evidence.json
```

Expected JSON fields:

- `status: pass`
- `uploadMode: multipart`
- `duplicateCompleteProven: true`
- `proxyReadyProven: true`
- `integrityStatus: verified` for local emulation
- hashed `assetId`, `storageKey`, `sourceObjectKey`, `proxyKey`, and base URL values only

## Test

```bash
cd /Users/hanfei/hc-agent-upload
PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_upload_pipeline
```

## Client Flow

1. Call `/v1/uploads/init`.
2. Upload to `uploadUrl` or multipart `parts[].uploadUrl`.
3. Call `/v1/uploads/{assetId}/complete`.
4. Poll `/v1/assets/{assetId}` until `status == "proxy_ready"`.
5. Optional team-pick flow: call `/v1/assets/{assetId}/team-scan`.
6. Call `/v1/assets/{assetId}/analysis-jobs`.
7. Poll the returned `/v1/analysis/jobs/{jobId}` as before.

The iOS client now prefers this asset path and falls back to `/v1/analysis/jobs -> uploadUrl -> /start` only when `/v1/uploads/init` is unavailable.
