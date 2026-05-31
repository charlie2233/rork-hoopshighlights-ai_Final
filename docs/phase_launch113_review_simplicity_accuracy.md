# Phase Launch113: Review Simplicity and Accuracy

Branch: `codex/phase-launch113-review-simple-accuracy`

## Goal

Make the iOS Review screen easier to use on small phones while preserving cloud-first ownership. The change focuses on helping users find uncertain, defensive, block, and steal clips before making an AI edit, without adding any local analysis or rendering.

## What Changed

- Review now hides zero-count filter chips instead of showing every possible filter all the time.
- Review keeps the currently selected filter visible even if the count changes, so the UI does not jump away from the user's selected view.
- Added a single `Check priority plays` card when there are clips that need attention:
  - uncertain team calls
  - uncertain review flags
  - blocks, steals, and other defensive plays
- Tapping the priority card opens the best matching review filter.
- Clip titles now wrap to two lines with dynamic scaling before truncation, improving small-phone and large-text compatibility.

## Architecture Check

This is an iOS control-surface/readability change only. It does not add local production video analysis, GPT calls, edit planning, rendering, composition, FFmpeg command generation, Remotion, Canva, or cloud cutover behavior. Cloud remains responsible for clip analysis, GPT selection, EditPlan, rendering, and storage.

## Accuracy Rationale

The app already keeps uncertain clips and defensive clips available for Review. The new card makes that behavior obvious and gives the user one tap to check those clips first, which reduces the chance that blocks, steals, or uncertain team moments are missed before AI Edit.

## Validation

- `git diff --check`: passed.
- Focused Review/GPT candidate tests: passed.
  - Result bundle: `/tmp/hoopclips-launch113-derived-data/Logs/Test/Test-HoopsClips-2026.05.31_14-38-39--0700.xcresult`
- iOS Debug simulator `build-for-testing`: passed.
  - Command used: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch113-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing`

Existing warnings observed but not introduced here:

- `CloudAnalysisService.swift`: `await` expressions with no async work.
- `VideoExportService.swift`: iOS 18 `AVAssetExportSession` deprecation/sendability warnings.

## Launch Status

This improves the in-app Review flow but does not prove the full internal TestFlight smoke. The remaining launch proof still requires a real installed TestFlight app running import, team scan, cloud analysis, Review, AI Edit render, preview, and share/open-in.
