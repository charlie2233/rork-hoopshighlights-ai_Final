# Phase Launch5 iOS Kill Switch Status

Date: 2026-05-22
Branch: `codex/phase-launch5-ios-kill-switch-status`

## Scope

- Added source support for a public Worker proxy of the editing service `/version` response at `GET /v1/editing/version`.
- Updated the iOS AI Edit client to fetch the proxied backend feature flags before render actions.
- Added an installed-app UI state for backend-paused AI Edit, live render, and revision kill switches.
- Updated the iOS-facing smoke script to fail before upload/render when staging reports AI Edit or live rendering disabled.
- Did not add local video analysis, local rendering, local composition, Remotion, Canva, secret logging, R2 credential logging, or full presigned URL logging.

## Runtime Behavior

The iOS app still uses the Worker as its cloud edit base URL. After this Worker source is deployed, the Worker proxies the editing service version endpoint without exposing secrets:

```text
GET /v1/editing/version -> editing service GET /version
```

The iOS app treats the response as advisory backend state:

- `aiEditEnabled=false`: disables the primary AI Edit action and shows a paused editing state.
- `aiEditLiveRenderEnabled=false`: disables render/re-render actions and shows a paused cloud rendering state.
- `aiEditRevisionEnabled=false`: disables revision buttons while leaving preview/share available for completed renders.
- Unknown or unavailable version state does not invent status; normal backend request errors remain authoritative.

## Validation

Control-plane typecheck:

```bash
npm --prefix services/control-plane run typecheck
```

Result: passed.

Control-plane editing proxy tests:

```bash
cd services/control-plane && npx tsx --test test/control-plane-editing-proxy.test.ts
```

Result:

```text
tests 9
pass 9
fail 0
```

Smoke script compile:

```bash
python3 -m py_compile services/editing/scripts/ios_ai_edit_client_smoke.py
```

Result: passed.

iOS Debug simulator build:

```text
XcodeBuildMCP build_sim -skipPackagePluginValidation
```

Result: passed after fixing a Swift getter return.

Focused iOS kill-switch tests:

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-derived-data \
  -resultBundlePath /tmp/hoopclips-launch5-kill-switch-tests.xcresult \
  -skipPackagePluginValidation \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditVersionFlagsDecodeLiveRenderKillSwitch \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditKillSwitchErrorsHaveFriendlyMessages
```

Result:

```text
** TEST SUCCEEDED **
```

iOS Debug build-for-testing:

```bash
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-derived-data \
  -skipPackagePluginValidation \
  build-for-testing
```

Result:

```text
** TEST BUILD SUCCEEDED **
```

Hygiene:

```text
git diff --check: passed
changed-line ASCII scan: passed
changed-line secret/presigned URL scan: only expected local test URL and secret header/key names
```

## 2026-05-23 Live Staging Refresh

The source route and local proxy tests existed, but the live staging Worker route was not deployed yet and returned a not-found response for:

```text
GET https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version
```

At that time, this phase was implemented in source but not proven live on staging.

## 2026-05-30 Live Staging Refresh

The staging Worker version proxy is now deployed and proven live on current `main`.

Evidence:

- Commit: `fd7313e0ca9eb9a53fbd08f03354cb11a96ce42d`.
- Secret-gated deploy proof: GitHub Actions run `26674350743`.
- Main push proof: `Cloud Edit Deploy Preflight` run `26674490395`.
- Live probe:

```sh
python3 scripts/staging_version_probe.py --expected-git-sha fd7313e0ca9eb9a53fbd08f03354cb11a96ce42d --json
```

Result: passed. The staging Worker returned the current commit SHA and non-secret AI Edit/GPT feature flag keys through `GET /v1/editing/version`, including `aiEditEnabled`, `aiEditLiveRenderEnabled`, `aiEditRevisionEnabled`, `aiEditTemplatePackEnabled`, `aiClipGptEditorEnabled`, `aiClipGptPlanEditEnabled`, `aiClipGptRevisionEnabled`, and `gptHighlightRerankerEnabled`.

## Remaining Blockers

- Real post-install TestFlight smoke still needs an online trusted iPhone with the internal staging build installed.
- Cloudflare/GCP CI credentials are still required for deploy and rollback proof.
- Statsig is still not the remote production flag source of truth.
- Production cloud cutover remains blocked by production Worker, Cloud Run, R2, D1, Sentry, Statsig, RevenueCat, Google, rollback, and beta proof gates.
