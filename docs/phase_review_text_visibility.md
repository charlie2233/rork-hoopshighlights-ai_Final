# Phase: Review Text Visibility

Branch: `codex/phase-review-readability-dynamic-type`

## Goal

Improve app readability on smaller phones and larger Dynamic Type settings without changing the cloud-first video architecture.

This is an iOS display-only change. It does not add local analysis, rendering, edit planning, or export logic.

## Changes

- Review clip cards now stack icon, confidence, and label content at accessibility Dynamic Type sizes.
- Review detail headers now stack detection badge, confidence, title, and context badges at accessibility Dynamic Type sizes.
- Clip labels can wrap to more lines at accessibility sizes, reducing hidden or clipped text.
- The `AI` detection badge now has an accessibility label.
- History project details now include a direct `Share Latest Export` action for the saved reel, instead of forcing users back through Export.
- Backend accuracy tests now protect selected-team review trimming for uncertain defensive families: blocks, steals, forced turnovers, and defensive stops should survive when made shots crowd the review pool.

## Evidence

### Commands

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-review-text-bft CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation build-for-testing
PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_selected_team_review_trim_keeps_uncertain_defensive_families -v
PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v
```

### Results

- `git diff --check`: passed.
- Focused selected-team defensive review regression: 1 test passed.
- Full backend pipeline quality suite: 53 tests passed.
- iOS Debug `build-for-testing`: `** TEST BUILD SUCCEEDED **`.

## Launch Notes

- This directly addresses review feedback that some title/text rows were cramped or hidden.
- This also addresses the request for a simpler share path from saved projects.
- Backend AI behavior is unchanged, but an accuracy regression test now locks in the selected-team defensive review guarantee.
- No GitHub Actions were used.
