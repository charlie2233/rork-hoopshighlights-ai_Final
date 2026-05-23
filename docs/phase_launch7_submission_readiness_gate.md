# Phase Launch7 Submission Readiness Gate

Date: 2026-05-23
Branch: `codex/phase-launch7-submission-readiness-gate`

## Scope

This branch adds a no-secret submission readiness preflight for internal TestFlight/App Store Connect decisions.

It does not submit a build, deploy the Worker, render video, analyze video, read credentials, print R2 credentials, print full presigned URLs, or message anyone. Browser/Computer/App Store Connect submission stays blocked until the preflight passes and a human can confirm any required high-impact third-party action.

## What Changed

- Added `scripts/submission_readiness_preflight.py`.
- Added `scripts/test_submission_readiness_preflight.py`.
- Reused the existing static backend/config gate from `scripts/launch_backend_config_preflight.py`.
- Added live staging Worker `/v1/editing/version` verification.
- Added iOS signing/export checks for bundle id, version, build, automatic signing, development team presence, and internal TestFlight export options.
- Added a bundle-id conflict check for the Rork release handoff, because the iOS project/export options use `atrak.charlie.hoopsclips` while the handoff still references `app.rork.hoopshighlights-ai`.
- Added upload artifact detection for `.xcarchive` or `.ipa`.
- Added deploy input presence checks without printing values.
- Added blocker-doc checks so known no-go launch evidence fails the preflight until refreshed.

## Current Result

HoopClips is **NO-GO for App Store/TestFlight submission** from this machine.

`python3 scripts/submission_readiness_preflight.py` result:

```text
HoopClips submission readiness preflight
pass=16 warn=3 fail=8
```

Failures:

- No `.xcarchive` or `.ipa` upload artifact was found under expected build output locations.
- The Rork release handoff references a bundle ID that does not match the iOS project/export options.
- Live staging Worker `GET /v1/editing/version` returned `404`.
- Required deploy input names are absent in the local environment: `CLOUDFLARE_API_TOKEN`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`, and `GCP_REGION`.
- Existing launch docs still record the missing installed TestFlight smoke.
- Existing launch docs still record the staging Worker version-route blocker.
- Existing launch docs still record missing Cloudflare deploy credential proof.
- Existing launch docs still record that live iOS kill-switch state is unproven through the Worker.

Warnings:

- Unrelated root Xcode folders are present and must not be staged: `HoopsClips.xcodeproj/`, `HoopsHighlightsAI.xcodeproj/`.
- No dedicated iOS upload workflow or fastlane lane exists; submission likely still needs manual Xcode/App Store Connect steps.

## Live Worker Evidence

Command:

```bash
curl -sS -o /tmp/hoopclips-submission-worker-version.json -w '%{http_code}\n' -H 'Accept: application/json' https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version
```

Result:

```text
404
```

Response body:

```json
{"requestId":"515d1363-8f81-4265-a622-da6399631e23","errorCode":"not_found","errorMessage":"Route not found.","failureReason":"Route not found."}
```

## Passing Evidence

Focused submission preflight tests:

```bash
python3 -m unittest scripts.test_submission_readiness_preflight -v
```

Result:

```text
Ran 3 tests in 0.005s
OK
```

Python syntax check:

```bash
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py
```

Result: passed.

Existing backend/config preflight reused by the submission gate:

```bash
python3 scripts/launch_backend_config_preflight.py
```

Result:

```text
HoopClips backend/config launch preflight
pass=57 warn=12 fail=0
```

Control-plane typecheck:

```bash
npm --prefix services/control-plane run typecheck
```

Result: `tsc -p tsconfig.json --noEmit` passed.

Control-plane tests:

```bash
npx tsx --test services/control-plane/test/*.test.ts
```

Result:

```text
tests 20
pass 20
fail 0
```

iOS backend tests:

```bash
PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests
```

Result:

```text
Ran 31 tests in 5.163s
OK
```

Editing service tests, run in an isolated temporary venv with `services/editing/requirements.txt` plus test-only `httpx`:

```bash
PYTHONPATH=services/editing:ios/backend /tmp/hoopclips-editing-tests-venv/bin/python -m unittest discover -s services/editing/tests
```

Result:

```text
Ran 44 tests in 38.146s
OK
```

Python syntax check for backend surfaces:

```bash
python3 -m py_compile $(rg --files services/editing ios/backend | rg '\.py$')
```

Result: passed.

iOS Debug simulator build:

```text
XcodeBuildMCP build_sim -skipPackagePluginValidation
```

Result: succeeded for scheme `HoopsClips` on iPhone 17 Pro simulator `7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2`. Existing Swift warnings remain, including Swift 6 isolation/deprecation warnings in the video analysis/export services.

iOS build-for-testing:

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch7-build-for-testing -skipPackagePluginValidation build-for-testing
```

Result:

```text
** TEST BUILD SUCCEEDED **
```

## Submission Decision

Do not submit to App Store Connect yet.

Required before submission:

1. Merge/publish the deploy workflow stack so `cloud-edit-deploy-preflight.yml` is available where operators can dispatch it.
2. Configure and verify `CLOUDFLARE_API_TOKEN` and GCP deploy inputs without printing secret values.
3. Deploy or refresh the staging Worker and prove `/v1/editing/version` returns the editing service non-secret feature flag payload.
4. Produce or locate the intended internal TestFlight `.xcarchive` or `.ipa`.
5. Install the internal TestFlight build on a trusted online iPhone and complete the full smoke: upload/import -> cloud analysis -> Review -> Export -> AI Edit -> render -> preview -> More Hype revision -> revised preview -> share/open-in.
6. Refresh launch docs so known no-go markers are replaced by current evidence.
7. Re-run `python3 scripts/submission_readiness_preflight.py`; only submit after it returns `pass=... fail=0`.

## Screenshots And Job IDs

No screenshots, App Store Connect submission IDs, TestFlight processing IDs, render job IDs, Worker deploy IDs, or rollback IDs were produced by this branch because the readiness gate correctly blocked submission.
