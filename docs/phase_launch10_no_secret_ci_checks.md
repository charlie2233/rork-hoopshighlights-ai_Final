# Phase Launch10 No-Secret CI Checks

Date: 2026-05-23
Branch: `codex/phase-launch10-no-secret-ci-checks`

## Scope

- Added no-secret CI codecheck lanes for internal TestFlight and cloud deploy readiness.
- Kept signed archive, App Store Connect upload, Worker deploy, Worker rollback, GCP deploy preflight, and secret-name verification behind explicit manual operations.
- Did not add, print, or depend on App Store Connect keys, Cloudflare tokens, GCP credentials, R2 credentials, or presigned URLs.
- Did not change app runtime behavior, cloud feature flags, template behavior, renderer behavior, or production cutover settings.

## Workflow Changes

### iOS Internal TestFlight Upload

`.github/workflows/ios-testflight-upload.yml` now supports:

- `pull_request` no-secret validation when the workflow, iOS project/config, export options, or iOS launch scripts change.
- Manual `workflow_dispatch` operation `codecheck`, which runs the same no-secret validation.
- Manual `workflow_dispatch` operations `preflight`, `archive`, and `upload`, which remain staging-environment and secret gated.

The codecheck job proves only:

- Internal staging build settings resolve to the expected staging Worker URLs, bundle id, version, build number, and launch mode.
- The internal TestFlight export options plist parses.
- Debug test targets compile for iOS Simulator with code signing disabled.

It does not create a signed archive, upload to App Store Connect, prove TestFlight processing, or prove installed-device smoke.

### Cloud Edit Deploy Preflight

`.github/workflows/cloud-edit-deploy-preflight.yml` now supports manual `workflow_dispatch` operation `codecheck`.

For `codecheck`, the existing `worker-dry-run` job runs:

- control-plane dependency install
- control-plane typecheck
- control-plane tests
- staging Worker dry-run bundle/binding validation

The deploy-secret verification job is skipped for `codecheck`. Manual `preflight`, `deploy`, and `rollback` still require the GitHub `staging` environment inputs and continue to prove real credential scope only when operators install those inputs.

## Remaining Blockers

- Real Cloudflare/GCP deploy credentials are still required for `operation=preflight`, `operation=deploy`, and `operation=rollback`.
- A signed `.xcarchive` or `.ipa` still requires App Store Connect/signing inputs.
- Installed TestFlight smoke is still required on a trusted online iPhone:
  upload/import -> cloud analysis -> Review -> Export -> AI Edit -> render -> preview -> More Hype revision -> revised preview -> share/open-in.
- Staging Worker `/v1/editing/version` still needs live default-branch deploy proof before launch signoff.

## Validation

Commands run:

```sh
git diff --check
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/ios-testflight-upload.yml"); YAML.load_file(".github/workflows/cloud-edit-deploy-preflight.yml"); puts "workflow yaml parses"'
bash ios/scripts/verify_internal_staging_config.sh
plutil -lint ios/exportOptions.testflight-internal.plist
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test
npm --prefix services/control-plane run deploy:staging:dry-run
xcodebuildmcp build_sim -skipPackagePluginValidation
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=<simulator-id>' -derivedDataPath /tmp/hoopclips-launch10-nosign-derived CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation
python3 scripts/submission_readiness_preflight.py
```

Results:

- `git diff --check`: passed.
- Workflow YAML parse: passed.
- Internal staging config verification: passed.
- Internal TestFlight export options plist lint: passed.
- Control-plane typecheck: passed.
- Control-plane tests: 20 passed.
- Staging Worker dry-run: passed with no deploy.
- XcodeBuildMCP simulator Debug build: passed.
- Direct no-signing `xcodebuild build-for-testing`: passed with `TEST BUILD SUCCEEDED`.
- Submission readiness preflight before commit: `pass=16 warn=1 fail=10`, with expected branch-local git dirty/untracked findings plus existing launch blockers.
