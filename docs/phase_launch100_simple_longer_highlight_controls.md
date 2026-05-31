# Phase Launch100: Simple Longer Highlight Controls

Branch: `codex/phase-launch100-simple-longer-highlight-controls`

## Goal

Respond to the latest internal testing feedback without changing the cloud-first architecture:

- Make reel length controls easier to find and use on small iPhones.
- Keep longer highlight targets available, including `4:30`.
- Reduce cramped/hidden text in Export AI Edit.
- Refresh the HoopClips app icon/brand mark because the installed app still appeared to use the old mark.

## Implementation

### iOS UI

- Replaced horizontal target-length scrollers with adaptive grids in import and AI Edit so options do not disappear offscreen on narrow devices.
- Renamed "Target Highlight" copy to "Target Reel Length" across supported app languages.
- Shortened AI Edit explanatory copy and moved plan-limit details behind a collapsed disclosure.
- Reduced Pro value rows shown inline so the Export screen is less crowded.
- Kept iOS as a control surface only. No local video analysis, rendering, or edit planning was added.

### Branding

- Regenerated both target-used and duplicate asset catalogs:
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
  - `ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
- New direction: bold athletic `HC` monogram, dark court base, basketball cue, gold clip slash, no AI/sparkle language.
- Verified the icon PNGs are RGB, not alpha PNGs.

### Candidate Pool Finding

Subagent review found the current GPT/candidate path is already configured around a high cap of `160` in the iOS/backend handoff:

- `ios/backend/app/config.py`
- `ios/backend/app/pipeline.py`
- `ios/backend/app/team_quick_scan.py`
- `ios/backend/app/editing.py`
- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`
- `services/editing/cloudbuild.yaml`

Increasing beyond `160` should be a coordinated backend/schema/test phase, not a UI-only tweak.

## Validation

Commands run:

```bash
git diff --check
```

Result: passed.

```bash
xcodebuildmcp build_sim
```

Result: passed.

Log:

```text
/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-31T19-57-22-541Z_pid49862_784e3cb4.log
```

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch100-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing
```

Result: passed with `** TEST BUILD SUCCEEDED **`.

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch100-derived-data CODE_SIGNING_ALLOWED=NO test-without-building -only-testing:HoopsClipsTests -skip-testing:HoopsClipsUITests
```

Result: broad unit run completed with 104 tests, 95 passed, 9 failed.

The failed subset was rerun narrowly:

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch100-derived-data CODE_SIGNING_ALLOWED=NO test-without-building -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditPolicySummaryExposesFreemiumCopy -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsStrongestCandidatesBeforeSixtyClipCap -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesMarkUncertainTeamOutcomeAndTiming -only-testing:HoopsClipsTests/CloudEditServiceTests/testFetchVersionUsesEditingVersionEndpointAndDecodesGptFlags -only-testing:HoopsClipsTests/CloudEditServiceTests/testDownloadRenderedVideoMapsExpiredStatusesToDownloadURLExpired -only-testing:HoopsClipsTests/CloudEditServiceTests/testFetchRenderHistoryUsesRenderJobsEndpointAndLimit -only-testing:HoopsClipsTests/FirebaseEmailAuthClientTests/existingAccountWithWrongPasswordStaysInvalidCredentials
```

Result: passed with `** TEST EXECUTE SUCCEEDED **`.

Interpretation: the broad suite still has residual isolation/order drift, but the failures did not reproduce when rerun directly.

## Launch Status

Not ready to call internal TestFlight launch complete from this phase alone.

Remaining launch evidence still needed:

- Installed-device TestFlight smoke with a real imported video.
- Staging cloud analysis and render smoke from upload through AI Edit preview/share.
- Confirmation that the cloud editing version check no longer times out on device.
- Any remaining import hang fixes from the Photos file-backed import path.
