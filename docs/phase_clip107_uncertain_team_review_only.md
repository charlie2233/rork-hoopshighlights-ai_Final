# Phase Clip107 - Uncertain Team Review Only

## Goal

Keep selected-team highlight quality strict while preserving recall for user review. When the cloud quick scan cannot prove jersey-color ownership at the selected-team confidence threshold, the clip should stay visible in Review, but it should not be auto-kept for export by default.

## Change

- `ios/backend/app/pipeline.py`
  - `_annotate_analysis_team_status` now demotes selected-team `uncertain` clips to `shouldAutoKeep=false`.
  - It also disables automatic slow motion on those uncertain clips.
  - The clip remains in the Review list when `includeUncertain=true`, so the user can still manually keep blocks, steals, or unclear highlights.
- `ios/backend/tests/test_pipeline_quality.py`
  - Added coverage that a matched selected-team clip remains auto-kept while an uncertain selected-team review clip is review-only.
- `ios/HoopsClips/HoopsClips/Models/CloudAnalysisTypes.swift`
  - `HighlightTeamSelection` now preserves `primaryColorHex` through encoding/decoding so detected jersey swatches survive request and persistence round trips.
- `ios/HoopsClips/HoopsClips/Models/ProjectHistory.swift`
  - Project history can persist the effective team selection, detected jersey-color teams, and cloud diagnostics.
- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`
  - Cloud analysis now applies the backend's effective `teamSelection` after analysis and restores persisted team scan state/diagnostics when reopening a project.
- `ios/HoopsClipsTests/HoopsClipsTests.swift`
  - Added Codable/persistence coverage for team swatch color, detected teams, and team-filter diagnostics.

## Why

The product goal is selected-team-only highlights, but uncertain clips should not disappear. This keeps unsure clips available for human review without silently rendering them as confirmed selected-team plays.

## Validation

Passed on May 29, 2026:

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_uncertain_selected_team_review_clip_is_not_auto_kept -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17' -only-testing:HoopsClipsTests/HoopsClipsTests/testHighlightTeamSelectionCodablePreservesPrimaryColorHex -only-testing:HoopsClipsTests/HoopsClipsTests/testPersistedProjectRecordStoresCloudTeamSelectionAndDiagnostics
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17'
xcodebuild build -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17'
git diff --check
```

Results:

- Focused backend test: 1 passed.
- Full pipeline quality tests: 46 passed.
- Backend test discovery: 180 passed.
- Editing-service test discovery: 98 passed.
- Focused iOS Swift tests: passed.
- iOS Debug build-for-testing: passed.
- iOS Debug build: passed.
- `git diff --check`: passed.

## Remaining Launch Proof

This is a behavior hardening change, not the final launch proof. The 85% target still requires a launch-grade labeled-footage accuracy report with selected-team makes, misses, blocks, steals, uncertain review clips, opponent highlights, and bad-window negatives.
