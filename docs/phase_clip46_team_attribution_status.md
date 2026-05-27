# Phase Clip46: Team Attribution Status

## Goal

Preserve selected-team uncertainty as explicit metadata from cloud analysis into iOS Review.

## Change

- Cloud analysis clips now include `teamAttributionStatus`: `all`, `matched`, `opponent`, or `uncertain`.
- The backend annotates final Review clips after selected-team filtering and visible-result trimming.
- iOS preserves `teamAttributionStatus` on `CloudClip` and `Clip`.
- Review shows `Team?` when the backend explicitly marks a clip `uncertain`, even if no `teamAttribution` object exists.

## Why

The product goal is to avoid losing plausible selected-team highlights, especially blocks, steals, forced turnovers, and jersey-color edge cases. Keeping uncertain clips is only useful if users can see why the clip is still present. This closes the missing-attribution case where a clip was reviewable but not visibly flagged.

## Architecture

- Cloud remains responsible for team quick scan, team attribution, selected-team filtering, and uncertainty classification.
- iOS only displays the cloud-owned status and lets users keep or discard clips.
- No iOS local analysis, rendering, composition, or timestamp logic changed.

## Validation

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_run_analysis_applies_quick_scan_before_selected_team_filter ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_team_status_marks_missing_attribution_uncertain_for_review -v`: passed, 2 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/models.py ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py`: passed.
- `mcp__xcodebuildmcp__.build_sim` for `ios/HoopsClips.xcodeproj`, scheme `HoopsClips`, Debug, iPhone 17 Pro simulator: passed.
- `mcp__xcodebuildmcp__.test_sim` with focused `-only-testing` arguments returned success but reported zero tests, so it was not counted as evidence.
- `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip45-dd CODE_SIGNING_ALLOWED=NO -only-testing:HoopsClipsTests`: passed.
  - New coverage: `HoopsClipsTests/testClipReviewBadgesMarkMissingTeamAttributionStatusUncertain`.
  - Existing coverage still passed: `HoopsClipsTests/testCloudClipMappingPreservesCloudMetadata`, `HoopsClipsTests/testClipReviewBadgesMarkUncertainTeamOutcomeAndTiming`, and `HoopsClipsTests/testCloudTeamScanPreparesJobThenStartSendsSelectedTeam`.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`: passed, 130 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`: passed, 40 tests.

## Launch Recommendation

Keep `includeUncertain=true` for internal beta and review `Team?` clips against labeled footage. Treat `Team?` as a recall-preserving user review state, not as proof of selected-team precision.
