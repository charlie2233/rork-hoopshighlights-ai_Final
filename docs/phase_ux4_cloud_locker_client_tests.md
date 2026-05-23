# Phase UX4 Cloud Locker Client Tests

Date: 2026-05-23
Branch: `codex/phase-ux4-cloud-locker-client-tests`
Base: `codex/phase-clip1-gpt-reranker-story-order`

## Scope

This branch adds iOS client coverage for the My AI Edits / Cloud Locker control-surface calls. It does not add local video analysis, rendering, composition, export, Remotion, or Canva behavior.

## What Changed

- Added Cloud Locker request/response tests in `ios/HoopsClipsTests/CloudEditServiceTests.swift`.
- Verified `fetchRenderHistory(installID:limit:)` calls `GET /v1/render-jobs` with `installId` and `limit`.
- Verified `fetchDownloadURL(renderJobID:installID:)` calls `GET /v1/render-jobs/{renderJobID}/download-url` and decodes a redacted download payload.
- Verified `requestStoredRender(editJobID:installID:)` calls `POST /v1/edit-jobs/{editJobID}/render` with `forceNew=true`, the install ID, and an `ios-locker-rerender-` idempotency key prefix.
- Kept the existing expired-download mapping test and made the suite serialized and `@MainActor` to avoid adding Swift 6 actor-isolation warnings.

## Validation

Focused Cloud Locker unit test:

```bash
Build iOS Apps test_sim -only-testing:HoopsClipsTests/CloudEditServiceTests CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment
```

Result:

```text
4 passed, 0 failed, 0 skipped
warnings: 0
```

Evidence:

```text
/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/test_sim_2026-05-23T18-49-51-853Z_pid51963_2d058081.log
/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-05-23T18-49-51-853Z_pid51963_ed91c286.xcresult
```

Diff check:

```bash
git diff --check
```

Result: passed.

Full iOS unit test target:

```bash
Build iOS Apps test_sim -only-testing:HoopsClipsTests CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment
```

Result:

```text
57 passed, 0 failed, 0 skipped
warnings: 0
```

Evidence:

```text
/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/test_sim_2026-05-23T18-51-14-644Z_pid51963_9e1d34e8.log
/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-05-23T18-51-14-644Z_pid51963_8ae19a8a.xcresult
```

Build for testing:

```bash
xcodebuild build-for-testing -quiet -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-ux4-locker-client-tests-bft-dd CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment
```

Result: passed with existing Swift concurrency/deprecation warnings in legacy local analysis/export/test code paths.

## Main Deploy Handoff Update

Before this branch, PR #8 was merged to `main` as commit `fe35d06`. The default-branch `Cloud Edit Deploy Preflight` workflow is now dispatchable.

Manual `operation=preflight` evidence:

```text
GitHub Actions run: 26339989518
headSha: fe35d0618190ce150383fb5a0fc968ee1517b517
Worker typecheck and dry run: success
Verify cloud edit deploy secrets: failed at missing input gate
Missing names: CLOUDFLARE_API_TOKEN, GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_DEPLOY_SERVICE_ACCOUNT, GCP_PROJECT_ID, GCP_REGION
```

No deploy, rollback, secret value, R2 credential, or presigned URL was produced.

## Remaining Blockers

- GitHub `staging` deploy inputs are still empty.
- Live staging Worker `/v1/editing/version` still returns `404`.
- No Worker deploy job ID or rollback job ID exists yet.
- iOS upload inputs and installed TestFlight smoke proof are still missing.
