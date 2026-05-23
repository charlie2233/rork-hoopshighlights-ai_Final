# Phase Launch8 iOS TestFlight Upload Automation

Date: 2026-05-23
Branch: `codex/phase-launch8-ios-testflight-upload-automation`

## Scope

This branch adds GitHub Actions automation for the internal staging TestFlight archive/upload path. It does not submit anything by itself, does not export video in iOS, does not analyze or render video locally, does not deploy the Worker, and does not print App Store Connect API key material, R2 credentials, or presigned URLs.

The workflow keeps the cloud-first product boundary intact: iOS packages and uploads the app; cloud backends still own analysis, edit planning, template policy, rendering, storage, and clipping enhancement.

## What Changed

- Added `.github/workflows/ios-testflight-upload.yml`.
- The workflow is manual-only through `workflow_dispatch`.
- The workflow uses the GitHub `staging` environment.
- The workflow supports `preflight`, `archive`, and `upload` operations.
- `preflight` and `archive` build/verify a signed internal-staging archive but do not upload to App Store Connect.
- `upload` runs the same archive checks and then calls `xcodebuild -exportArchive` with `ios/exportOptions.testflight-internal.plist`.
- The workflow uses `ios/scripts/materialize_local_secrets.sh` and `ios/scripts/verify_internal_staging_config.sh`.
- The workflow requires App Store Connect API key inputs and passes them to `xcodebuild` through `-authenticationKeyPath`, `-authenticationKeyID`, and `-authenticationKeyIssuerID`.
- The workflow removes the temporary `.p8` key file in an `always()` cleanup step.
- Bumped the next iOS build number from `3` to `4` so the next internal TestFlight upload does not reuse the historical build `3`.
- The submission preflight now validates `.xcarchive` metadata for bundle ID, marketing version, and build number instead of treating any archive directory as upload-ready.
- Updated `scripts/submission_readiness_preflight.py` so the submission gate verifies:
  - the workflow exists,
  - it uses internal staging config,
  - it uses the internal TestFlight export options,
  - it has an explicit upload operation,
  - required iOS upload input names are present locally or in the GitHub `staging` environment.

## Required GitHub Staging Inputs

Secrets:

```text
HOOPS_DEVELOPMENT_TEAM
HOOPS_REVENUECAT_API_KEY
HOOPS_GOOGLE_CLIENT_ID
HOOPS_GOOGLE_REVERSED_CLIENT_ID
HOOPS_FIREBASE_AUTH_API_KEY
HOOPS_SENTRY_DSN
APP_STORE_CONNECT_KEY_ID
APP_STORE_CONNECT_ISSUER_ID
APP_STORE_CONNECT_API_KEY_BASE64
```

Variables:

```text
HOOPS_PRIVACY_POLICY_URL
HOOPS_TERMS_OF_SERVICE_URL
```

`APP_STORE_CONNECT_API_KEY_BASE64` should be the base64-encoded contents of the App Store Connect `.p8` API key file. Do not paste raw key contents into docs, logs, or shell history.

## Current Result

Fresh internal-staging archive created locally:

```text
/tmp/HoopsClips-Launch8-InternalStaging.xcarchive
```

Archive metadata:

```text
CFBundleIdentifier: atrak.charlie.hoopsclips
CFBundleShortVersionString: 1.0.0
CFBundleVersion: 4
HOOPSAppEnvironment: internal_staging
HOOPSCloudLaunchMode: internal_only
HOOPSCloudAnalysisBaseURL: https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
HOOPSCloudEditBaseURL: https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
```

`python3 scripts/submission_readiness_preflight.py --archive-path /tmp/HoopsClips-Launch8-InternalStaging.xcarchive` result before this branch is committed:

```text
HoopClips submission readiness preflight
pass=18 warn=2 fail=8
```

Expected after this branch is committed and rerun from a clean tracked worktree:

```text
pass=19 warn=1 fail=7
```

Remaining failures after this branch:

- Live staging Worker `GET /v1/editing/version` returns `404`.
- Required Cloudflare/GCP deploy input names are still missing.
- Existing launch docs still record the missing installed TestFlight smoke.
- Existing launch docs still record the staging Worker version-route blocker.
- Existing launch docs still record missing Cloudflare deploy credential proof.
- Existing launch docs still record that live iOS kill-switch state is unproven through the Worker.
- Required iOS/App Store Connect upload input names are still missing from local env and the GitHub `staging` environment.

The previous "no upload automation" warning is resolved by this branch.

## Validation

Internal staging config:

```bash
bash ios/scripts/verify_internal_staging_config.sh
```

Result:

```text
Internal staging Release config is explicit and cloud-enabled for staging only.
```

Signed archive:

```bash
xcodebuild archive -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Release -destination 'generic/platform=iOS' -archivePath /tmp/HoopsClips-Launch8-InternalStaging.xcarchive -derivedDataPath /tmp/hoopclips-launch8-internal-staging-archive-derived -xcconfig ios/HoopsClips/HoopsClips/Config/InternalStaging.xcconfig -allowProvisioningUpdates -hideShellScriptEnvironment
```

Result: passed with existing Swift concurrency/deprecation warnings.

iOS Debug simulator build:

```text
Build iOS Apps build_sim
```

Result: passed.

iOS build-for-testing:

```bash
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch8-build-for-testing-derived CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment
```

Result: passed with existing Swift concurrency/deprecation warnings.

iOS simulator tests:

```text
Build iOS Apps test_sim
```

Result:

```text
TEST EXECUTE SUCCEEDED
```

Notes: the MCP call timed out at 120 seconds, but the underlying `xcodebuild test-without-building` continued and completed successfully. The result bundle is under `~/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-05-23T17-32-08-366Z_pid9039_b4990d02.xcresult`. AI Edit fixture-guarded UI tests were skipped; launch/settings/UI smoke tests passed.

Workflow YAML parse:

```bash
ruby -e 'require "yaml"; ARGV.each { |f| YAML.load_file(f); puts "#{f}: ok" }' .github/workflows/ios-testflight-upload.yml
```

Result:

```text
.github/workflows/ios-testflight-upload.yml: ok
```

Focused tests:

```bash
python3 -m unittest scripts.test_submission_readiness_preflight scripts.test_launch_backend_config_preflight -v
```

Result:

```text
Ran 9 tests in 0.035s
OK
```

Editing service tests:

```bash
/tmp/hoopclips-editing-test-venv313/bin/python -m pytest services/editing/tests -q
```

Result:

```text
44 passed in 25.98s
```

Note: Python 3.14 could not build the pinned `pydantic-core` dependency; the suite was rerun in a temporary Python 3.13 venv.

Control-plane typecheck:

```bash
npm --prefix services/control-plane run typecheck
```

Result: passed.

Control-plane tests:

```bash
npx --yes tsx --test services/control-plane/test/*.test.ts
```

Result:

```text
tests 20
pass 20
fail 0
```

Note: bare `node --test --experimental-strip-types` could not resolve the repo's extensionless TypeScript harness import, so the suite was rerun with `tsx`.

Workflow run-block shell syntax:

```bash
ruby - <<'RUBY'
require 'yaml'
workflow = YAML.load_file('.github/workflows/ios-testflight-upload.yml')
runs = workflow.fetch('jobs').values.flat_map { |job| job.fetch('steps', []) }.map { |step| step['run'] }.compact
runs.each_with_index do |script, index|
  path = "/tmp/hoopclips-workflow-run-#{index}.sh"
  File.write(path, script)
  system('bash', '-n', path) or abort("bash -n failed for run block #{index}")
end
puts "checked #{runs.length} run blocks"
RUBY
```

Result:

```text
checked 10 run blocks
```

Python syntax check:

```bash
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py
```

Result: passed.

Submission preflight:

```bash
python3 scripts/submission_readiness_preflight.py --archive-path /tmp/HoopsClips-Launch8-InternalStaging.xcarchive
```

Result before commit:

```text
submission automation: pass
ios upload inputs: fail
```

No workflow dispatch, App Store Connect export/upload, TestFlight processing, or installed-app smoke was run in this branch.

## Submission Decision

Still **NO-GO** for App Store Connect submission.

Required next steps:

1. Add the required iOS/App Store Connect upload inputs to the GitHub `staging` environment.
2. Add the required Cloudflare/GCP deploy inputs to the GitHub `staging` environment.
3. Refresh the staging Worker and prove `/v1/editing/version` returns non-secret editing feature flag state.
4. Run `iOS Internal TestFlight Upload` with `operation=preflight`.
5. Run `iOS Internal TestFlight Upload` with `operation=upload` only after the Worker/deploy gates pass.
6. Install the TestFlight build on a trusted online iPhone and run the full post-install smoke.
