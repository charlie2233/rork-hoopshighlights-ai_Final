# Phase Launch111: Review Accuracy and Badge Visibility

Branch: `codex/phase-launch111-review-accuracy-visibility`

## Goal

Improve the Review screen where users decide which clips are accurate enough to keep. This phase focuses on safer quick actions, clearer defensive/team-check handling, and keeping badge text visible on smaller phones and larger text settings.

The phase also refreshes the shipped app icon/brand mark after device testing showed the installed app still did not clearly show the new HoopClips product logo.

## What Changed

- `Skip Low` now skips only safe low-confidence clips.
- Low-confidence clips that need review, contain uncertain team attribution, or represent defensive events such as blocks, steals, forced turnovers, or defensive stops stay kept for human review.
- Review badge rows now use `ViewThatFits` and fall back to an adaptive grid when team/defense/review badges do not fit on one line.
- Badge text can wrap and scale instead of clipping.
- Added a focused unit test proving low-confidence defensive/review clips are protected from the quick skip action.
- Replaced the iOS AppIcon and in-app `BrandMark` PNGs in both asset catalogs with a cleaner product mark: bold `HC`, dark court field, orange basketball/rim curve, and red/orange motion slashes.
- Removed the alpha channel from the refreshed PNGs so App Store/TestFlight icon validation does not reject the icon.
- Bumped `CURRENT_PROJECT_VERSION` from `7` to `8` for the next install/TestFlight build.

## Architecture Check

This stays inside iOS review UX and candidate decision controls. It does not add local video analysis, local rendering, composition, FFmpeg generation, or GPT execution. Cloud analysis, GPT editing, edit planning, rendering, and storage remain backend-owned.

## Validation

Passed:

- `git diff --check`
- `sips -g pixelWidth -g pixelHeight -g hasAlpha ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
  - AppIcon: `1024x1024`, `hasAlpha: no` in both asset catalogs.
  - BrandMark: `512x512`, `hasAlpha: no` in both asset catalogs.
- Focused iOS tests:
  - `testDiscardLowConfidencePreservesReviewAndDefensiveClips`
  - `testKeepHighConfidenceDoesNotAutoKeepNeedsReviewClips`
  - `testCloudEditCandidateRankingReservesDefenseAndReviewClipsBeforeCap`
  - Result: `** TEST SUCCEEDED **`
  - Result bundle: `/tmp/hoopclips-launch111-derived-data/Logs/Test/Test-HoopsClips-2026.05.31_14-08-59--0700.xcresult`
- iOS Debug simulator `build-for-testing`
  - Result: `** TEST BUILD SUCCEEDED **`

Known existing warnings observed during build:

- `CloudAnalysisService.swift`: existing `no 'async' operations occur within 'await' expression` warnings.
- `VideoExportService.swift`: existing AVAssetExportSession deprecation/sendability warnings.

## Launch Status

This improves review accuracy and phone compatibility, but it does not prove internal TestFlight readiness by itself. A real installed-device smoke still needs to cover import, team selection, cloud analysis, Review, AI Edit render, preview, and share/open-in.
