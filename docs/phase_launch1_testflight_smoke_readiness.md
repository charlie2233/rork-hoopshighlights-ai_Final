# Phase Launch1 TestFlight Smoke Readiness

Date: 2026-05-22
Branch: `codex/testflight-smoke-readiness-no-device`
Base: `cd70efc`

## Result

This branch hardens the no-device launch smoke tooling, but it does not claim the installed TestFlight app passed.

The real post-install smoke still needs an online trusted iPhone with the internal staging TestFlight build installed. The deployed staging Worker also appears stale for the iOS `/v1/editing/version` route, so a full Worker-mediated render/revision smoke is blocked until the Worker deployment is refreshed.

No secrets, R2 credentials, real storage object keys, or full presigned URLs were printed.

## What Changed

- Extended `services/editing/scripts/ios_ai_edit_client_smoke.py` beyond the initial render/download path.
- The script now requests `make_more_hype`, renders that revision, waits for the exact revision render job, downloads the revised MP4, and ffprobes both downloaded outputs.
- Success output now reports IDs, feature flags, local downloaded paths, media probes, and revised-plan summary only.
- Failure output recursively redacts URL, storage object key, secret, and credential fields before printing JSON details.

## Evidence

Commands run from `/Users/hanfei/rork-hoopshighlights-ai_Final`.

```bash
git pull --ff-only
```

Result: `Already up to date.`

```bash
python3 scripts/launch_backend_config_preflight.py
```

Result: `pass=57 warn=12 fail=0`.

Important warnings still present:

- Production Worker cutover is intentionally absent.
- Top-level Worker D1/R2 config is placeholder-only; internal beta should use `env.staging`.
- Editing backend Sentry DSN, Statsig remote flag source, and RevenueCat REST verifier remain production/internal-beta gates.
- Launch docs still record production cutover and CI credential blockers.

```bash
./ios/scripts/verify_internal_staging_config.sh
```

Result:

```text
HOOPS_APP_ENV=expected
HOOPS_CLOUD_LAUNCH_MODE=expected
HOOPS_CLOUD_ANALYSIS_BASE_URL=expected
HOOPS_CLOUD_EDIT_BASE_URL=expected
PRODUCT_BUNDLE_IDENTIFIER=expected
MARKETING_VERSION=expected
CURRENT_PROJECT_VERSION=expected
INFOPLIST_FILE=expected
Internal staging Release config is explicit and cloud-enabled for staging only.
```

```bash
curl -sS -D /tmp/hoopclips-worker-version.headers \
  -o /tmp/hoopclips-worker-version.json \
  -w '%{http_code}' \
  https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version
```

Result: `404`.

Body:

```json
{"requestId":"2edb6c92-4eb7-4eb7-990c-943025ba5a9b","errorCode":"not_found","errorMessage":"Route not found.","failureReason":"Route not found."}
```

This blocks the iOS-facing smoke script before upload/render. Local source code has the proxy route, so the deployed staging Worker needs a refresh before the full smoke can pass.

```bash
curl -sS -o /tmp/hoopclips-revision-probe.json \
  -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -H 'x-trace-id: phase-launch1-route-probe' \
  --data '{"installId":"smoke-install-ios-ai-edit","command":"make_more_hype"}' \
  https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/edit-jobs/edit_fake_probe/revise
```

Result: `404`.

Body:

```json
{"requestId":"0da4dd4b-aa22-4c9c-91cd-3d5540392ba0","errorCode":"edit_job_not_found","errorMessage":"Edit job was not found.","failureReason":"Edit job was not found."}
```

This is the expected response for a fake edit job and confirms the deployed Worker recognizes at least the revision proxy path.

## Validation

```bash
python3 -m py_compile services/editing/scripts/ios_ai_edit_client_smoke.py
```

Result: passed.

```bash
PYTHONPATH=services/editing/scripts python3 - <<'PY'
from ios_ai_edit_client_smoke import sanitize_for_log
payload = {
    "downloadUrl": "https://example.test/file.mp4?X-Amz-Signature=abc",
    "nested": [{"sourceObjectKey": "uploads/example/source.mp4", "safe": "ok"}],
    "safe": "keep-me",
}
sanitized = sanitize_for_log(payload)
assert sanitized["downloadUrl"] == "[redacted]"
assert sanitized["nested"][0]["sourceObjectKey"] == "[redacted]"
assert sanitized["nested"][0]["safe"] == "ok"
assert sanitized["safe"] == "keep-me"
print("sanitize_for_log redaction check passed")
PY
```

Result: `sanitize_for_log redaction check passed`.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
```

Result: `Ran 37 tests in 69.161s` and `OK`.

```bash
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-derived-data \
  build-for-testing \
  CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation
```

Result: `** TEST BUILD SUCCEEDED **`.

The build-for-testing output still includes pre-existing Swift warnings in local analysis/export code such as `VideoAnalysisService.swift`, `CloudAnalysisService.swift`, and `VideoExportService.swift`. This branch does not modify those iOS paths.

```text
XcodeBuildMCP build_sim extraArgs=["-skipPackagePluginValidation"]
```

Result: simulator Debug build succeeded in 11.905s with no reported diagnostics.

```bash
git diff --check
```

Result: passed.

```bash
rg -n "X-Amz-|Signature=|downloadUrl|uploadUrl|sourceObjectKey|outputObjectKey|renderLogObjectKey|SECRET|ACCESS_KEY|R2_" \
  docs/phase_launch1_testflight_smoke_readiness.md \
  services/editing/scripts/ios_ai_edit_client_smoke.py
```

Result: matches are limited to script field names and redaction test literals; no secret values, credentials, real storage object keys, or full presigned URLs are recorded in this doc.

## Remaining Blockers

- Real installed-TestFlight smoke is still blocked by missing online physical device access from this environment.
- Full Worker-mediated AI Edit smoke is blocked until staging Worker deploy includes `GET /v1/editing/version`.
- CI deploy/rollback remains blocked by missing GitHub staging environment secrets/variables and workflow availability on the default branch.
