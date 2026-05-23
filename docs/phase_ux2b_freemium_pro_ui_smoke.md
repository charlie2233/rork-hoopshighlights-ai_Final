# Phase UX2b Freemium Pro UI Smoke

## Branch

- Branch: `codex/phase-ux2b-freemium-pro-ui-hardening`
- Base commit: `25dfd91` (`Harden TestFlight smoke readiness`)
- Scope: tighten Free/Pro AI Edit UI smoke coverage, keep Pro template locks honest, and remove timeline wording that could overstate backend progress before cloud render status exists.

## Current Product State

- The iOS app has RevenueCat/App Store upgrade surfaces when configured.
- This branch does not add subscription purchase mechanics, local rendering, local analysis, or unsupported Pro render behavior.
- Locked Pro templates remain informational gates; tapping them must not start rendering or create a revision job.
- AI Edit work status must come from cloud render state when available. Pending client-side checklist rows are labeled as a checklist until the server reports progress.

## Validation Commands

```sh
git diff --check
```

Result: passed.

```sh
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-ux2b-hardening-final-dd \
  build CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation
```

Result: passed. `/tmp/hoopclips-ux2b-hardening-final-debug-build.log` ended with `** BUILD SUCCEEDED **`.

```sh
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-ux2b-hardening-final-bft-dd \
  build-for-testing CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation
```

Result: passed. `/tmp/hoopclips-ux2b-hardening-final-bft.log` ended with `** TEST BUILD SUCCEEDED **`.

```sh
xcodebuild test -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-ux2b-hardening-flag9-dd \
  -resultBundlePath /tmp/hoopclips-ux2b-hardening-ui-smoke-flag9.xcresult \
  -only-testing:HoopsClipsUITests/HoopsClipsUITests/testAIEditFreemiumProUXSmoke \
  OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE' \
  -skipPackagePluginValidation
```

Result: passed. `xcresulttool get test-results summary` reported `result: Passed`, `passedTests: 1`, `failedTests: 0`, `skippedTests: 0`.

The run kept two screenshot attachments in the xcresult:

- `UX2B Free Plan And Pro Value Cards`
- `UX2B Locked Pro Template Info Sheet`

## UI Smoke Coverage

The focused `testAIEditFreemiumProUXSmoke` now asserts the Free plan card and exact Free limits:

- `Current plan: Free`
- `Standard render queue`
- `720p max export`
- `HoopClips watermark/outro included`
- `3 AI edits/day`
- `3 revisions/edit`
- `Videos stored for 14 days`
- `My AI Edits: rendered videos expire in 14 days on Free.`

It also asserts the Pro value card, the App Store upgrade CTA, the Pro benefits CTA, and current Pro upgrade rows:

- `Upgrade with App Store`
- `See Pro benefits`
- `Priority rendering`
- `1080p clean exports`
- `No required watermark`
- `No required HoopClips outro`
- `Longer videos`
- `More revisions`
- `Longer cloud storage`
- `Pro template packs`

Locked template coverage now checks all four Pro template IDs:

- `export.aiEdit.proTemplate.recruitingReel`
- `export.aiEdit.proTemplate.cinematicMixtape`
- `export.aiEdit.proTemplate.nbaRecap`
- `export.aiEdit.proTemplate.teamHighlight`

Tapping the Team Highlight locked template must open `export.aiEdit.proInfoSheet`, show `Upgrade with App Store`, and not expose `Buy`, `Subscribe`, `Render Revision`, `export.aiEdit.renderRevisionButton`, or `export.aiEdit.preview`.

The smoke also asserts that the locked-template path does not show static text containing `thinking` or `ETA`, then closes the sheet without starting a render.

## Changed Files

- `ios/HoopsClips/HoopsClips/Views/AIEditView.swift`
  - Moved the Pro value card CTAs above the chip grid so Free users see the upgrade and benefit actions before the dense Pro value list.
  - Reworded the work timeline footer so fallback checklist rows are not presented as live cloud progress before `renderStatus?.workTimeline` is available.
- `ios/HoopsClipsUITests/HoopsClipsUITests.swift`
  - Expanded UX2b coverage for exact Free limits, Pro value copy, App Store upgrade labels, all locked Pro templates, no render/preview leakage from a locked template sheet, and no `thinking`/`ETA` copy.
  - Hardened scroll helpers for nested Export scroll views by targeting the largest visible scroll view and searching both directions.

## Architecture Checks

- No iOS video analysis added.
- No iOS rendering, composition, or export pipeline added.
- No Remotion or Canva path added to iOS.
- No secrets, R2 credentials, or presigned URLs were added to logs or documentation.
- No fake backend work, fake waits, or fake ETA copy was added.

## Remaining Blockers

- Full installed-device TestFlight UX2b smoke is still required on a trusted iPhone after the app is installed from TestFlight.
- Live watermark/outro upsell verification still depends on a completed cloud AI Edit work receipt; this branch only hardens the static Free/Pro UX smoke path.
- Cloud Locker render-history download/re-render coverage remains the separate UX4 phase; this UX2b run only verifies the Free retention copy in the plan card.
