# Phase UX2b Freemium Pro UI Smoke

## Branch

- Branch: `codex/phase-ux2b-freemium-pro-ui-smoke`
- Base commit: `c6d294a` (`codex/phase-ux2-freemium-pro-experience`)
- Scope: verify Free/Pro AI Edit UX evidence, stable accessibility IDs, and no-payment placeholder behavior.

## Validation Commands

```sh
git diff --check
```

Passed.

```sh
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-ux2b-dd \
  build CODE_SIGNING_ALLOWED=NO
```

Passed: `/tmp/hoopclips-ux2b-build.log` ended with `** BUILD SUCCEEDED **`.

```sh
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-ux2b-dd \
  build-for-testing CODE_SIGNING_ALLOWED=NO
```

Passed after the final accessibility patch: `/tmp/hoopclips-ux2b-bft-3.log` ended with `** TEST BUILD SUCCEEDED **`.

## Simulator Setup

```sh
xcrun simctl shutdown all || true
xcrun simctl erase all
xcrun simctl boot A46E2157-77ED-42CE-959D-65C068681A47
xcrun simctl bootstatus A46E2157-77ED-42CE-959D-65C068681A47 -b
```

Result: iPhone 17 simulator booted and reached terminal boot status.

## UI Evidence

Manual simulator launch used the existing DEBUG smoke fixture:

```sh
env \
  SIMCTL_CHILD_HOOPS_UI_SMOKE_MODE=1 \
  SIMCTL_CHILD_HOOPS_AI_EDIT_TEST_FIXTURE=staging_render_ready \
  SIMCTL_CHILD_HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  SIMCTL_CHILD_HOOPS_CLOUD_EDIT_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  SIMCTL_CHILD_HOOPS_SMOKE_WORKER_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  SIMCTL_CHILD_HOOPS_SMOKE_INSTALL_ID=phase-ux2b-manual-sim-smoke \
  SIMCTL_CHILD_HOOPS_SMOKE_SOURCE_OBJECT_KEY=uploads/25a101ba8d234fd98094bd112276161f/source.mp4 \
  xcrun simctl launch --terminate-running-process \
  --stdout=/tmp/hoopclips-ux2b-manual-stdout.log \
  --stderr=/tmp/hoopclips-ux2b-manual-stderr.log \
  A46E2157-77ED-42CE-959D-65C068681A47 \
  atrak.charlie.hoopsclips --hoops-ai-edit-live-smoke
```

Screenshots:

- Player launch smoke: `docs/phase_ux2b_artifacts/01_manual_launch.jpg`
- Export AI Edit top section: `docs/phase_ux2b_artifacts/02_export_ai_edit_top.jpg`
- Free plan retention copy and Pro value card: `docs/phase_ux2b_artifacts/03_free_plan_pro_value.jpg`
- Pro template placeholders: `docs/phase_ux2b_artifacts/06_template_pack_mid.jpg`
- Locked Pro template info sheet: `docs/phase_ux2b_artifacts/07_pro_template_info_sheet.jpg`

## What Free Users See

Verified in the Export AI Edit UI and accessibility hierarchy:

- `Current plan: Free`
- `Standard render queue`
- `HoopClips keeps editing in the cloud. Pro gets priority rendering.`
- `Free: 3 AI edits/day, 3 revisions/edit, 720p max, watermark/outro included.`
- `My AI Edits: rendered videos expire in 14 days on Free.`
- Background render copy: `You can leave the app - HoopClips will keep editing in the cloud. Come back anytime to preview your finished reel.`

## What Pro Placeholder Shows

Verified in the Export AI Edit UI:

- `Upgrade to Pro`
- `Priority rendering`
- `1080p clean exports`
- `No required watermark`
- `No required HoopClips outro`
- `Longer videos`
- `More revisions`
- `Longer cloud storage`
- `Pro template packs`

Locked template placeholders are visible and marked Pro:

- `Recruiting Reel Pro`
- `Cinematic Mixtape Pro`
- `NBA Recap Pro`
- `Team Highlight Pro`

Tapping `Recruiting Reel Pro` opens an informational Pro Template sheet. The sheet states that this build only adds honest Pro placeholders and policy-aware UX, and that it does not enable payments or unsupported Pro rendering.

## Accessibility IDs

Added or verified stable identifiers:

- `export.aiEdit.planCard.free`
- `export.aiEdit.proValueCard`
- `export.aiEdit.proTemplate.recruitingReel`
- `export.aiEdit.proTemplate.cinematicMixtape`
- `export.aiEdit.proTemplate.nbaRecap`
- `export.aiEdit.proTemplate.teamHighlight`
- `export.aiEdit.proInfoSheet`
- `export.aiEdit.workReceipt`
- `export.aiEdit.watermarkUpsell`

The sheet-level SwiftUI identifier did not appear as a standalone node in the simulator hierarchy, so the same `export.aiEdit.proInfoSheet` identifier is also applied to visible sheet content.

## Behavior Checks

- Locked Pro template tap opened the Pro info sheet.
- Locked Pro template did not start a render.
- No Buy or Subscribe UI is present in the Pro template sheet.
- No payment implementation was added.
- No local analysis or local rendering was added.
- No fake ETA was added.
- No artificial normal-render wait was added.
- Manual launch stdout/stderr did not print presigned URLs.

## XCTest Runner Limitation

Focused XCTest command:

```sh
xcodebuild test -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=A46E2157-77ED-42CE-959D-65C068681A47' \
  -derivedDataPath /tmp/hoopclips-ux2b-dd \
  -resultBundlePath /tmp/hoopclips-ux2b-freemium-ui-smoke.xcresult \
  -only-testing:HoopsClipsUITests/HoopsClipsUITests/testAIEditFreemiumProUXSmoke \
  CODE_SIGNING_ALLOWED=NO \
  OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE'
```

Result: failed before test execution. The simulator denied launching the UI test runner:

```text
FBSOpenApplicationServiceErrorDomain Code=1
Simulator device failed to launch atrak.charlie.hoopsclips.uitests.xctrunner.
FBProcessExit Code=64
RBSRequestErrorDomain Code=5
The request was denied by service delegate (SBMainWorkspace).
```

Retry without `CODE_SIGNING_ALLOWED=NO` produced the same runner launch failure. This is a simulator/XCTest runner launch issue, not evidence of a product failure, because the app builds, build-for-testing succeeds, the app launches manually, and manual UI evidence confirms the UX2 Free/Pro surfaces.

## Remaining Blockers

- Full focused XCTest screenshot attachments were not produced because the simulator denied launching `HoopsClipsUITests-Runner.app`.
- AI Work Receipt screenshot was not rerun live in this branch to avoid turning UX2b into another cloud-render smoke. The existing live AI Edit flow remains covered by prior RC/live-smoke evidence, and this branch only changed UI identifiers and placeholder UX surfaces.
- Legacy non-AI export options still show existing Pro-gated export controls; UX2b only verifies the AI Edit Pro template placeholders and plan-tier UX.
