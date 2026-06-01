# Phase Launch156 - Review Evidence and Defensive Accuracy

## Goal

Improve app and AI accuracy without touching logo work. This phase focuses on defensive highlight recall and clearer Review evidence:

- Keep blocks, steals, forced turnovers, deflections, charges, takeaways, interceptions, poked/ripped loose balls, and loose-ball recoveries in the cloud/GPT candidate path.
- Surface those defensive clips clearly in iOS Review.
- Keep Review evidence readable on smaller screens and larger Dynamic Type.

## Architecture

- Cloud/backend still owns analysis, candidate expansion, GPT rerank, edit planning, rendering, and storage.
- iOS still only uploads, reviews clips, sends selected candidates/user intent, shows status, previews, downloads, and shares.
- No local iOS rendering, FFmpeg planning, or GPT execution was added.
- No full videos are sent to GPT by this change.

## Changes

- `ios/backend/app/editing.py`
  - Expanded defensive event classification.
  - Defensive labels now include swats/rejections, takeaways, interceptions, deflections, charges, poked/ripped loose, and loose-ball events.
  - `is_defensive_event_like_clip` now uses the shared defensive family classifier so EditPlan validation and GPT prep agree.

- `ios/backend/app/pipeline.py`
  - Aligned analysis review reserve labels with backend edit planning.
  - More defensive-pressure clips survive review trimming before the user/GPT step.

- `services/editing/editing_app/gpt_reranker.py`
  - Aligned GPT defensive reserve buckets with the backend classifier.
  - Takeaways map to `steal`; deflections, charges, and loose-ball recoveries map to `forced_turnover`.

- `ios/HoopsClips/HoopsClips/Models/Clip.swift`
  - Review evidence now describes defensive-pressure and possession-change clips as defensive highlights, not generic high-confidence moments.

- `ios/HoopsClips/HoopsClips/Views/ReviewView.swift`
  - Review priority copy now calls out forced turnovers.
  - Defensive badges recognize forced turnovers and stops.
  - Evidence row titles/check badges wrap with `ViewThatFits`; detail rows allow more lines for Dynamic Type.

## Tests

Local validation run on May 31, 2026:

- `git diff --check`
  - Passed.

- `ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py ios/backend/app/pipeline.py services/editing/editing_app/gpt_reranker.py`
  - Passed.

- `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent`
  - Passed: 104 tests.

- `ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker`
  - Passed: 63 tests.

- `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_defensive_label_classifier_ignores_stop_and_pop_jumpers ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_defensive_label_classifier_requires_forced_turnover_context ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_review_trim_reserves_strong_defensive_clip_when_scoring_fills_cap ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_team_diagnostics_split_forced_turnovers_and_defensive_stops`
  - Passed: 4 tests.

- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch156-derived-data test -only-testing:HoopsClipsTests CODE_SIGNING_ALLOWED=NO -quiet`
  - Passed: full `HoopsClipsTests` target.

- `mcp__xcodebuildmcp.build_sim`
  - Passed before derived-data cleanup.
  - Existing warnings remained in `CloudAnalysisService.swift` and `VideoExportService.swift`; this phase did not introduce them.

## Notes

- The first simulator test attempt failed because the Mac had only about 303 MiB free. Xcode could not create result bundles or log folders.
- Generated Xcode DerivedData and HoopClips temp build artifacts were cleared, restoring about 32 GiB free.
- The full MCP simulator test call timed out at 120 seconds; after cleanup, shell `xcodebuild` completed the full `HoopsClipsTests` target successfully.

## Launch Recommendation

This improves recall for important defensive highlights, especially when labels are not exactly `Block` or `Steal`. It does not replace the real internal TestFlight smoke. Before submission, still run the real-device path:

install app -> import/upload -> cloud analysis -> Review -> Export -> AI Edit -> render -> preview -> More Hype revision -> revised preview -> share/open-in.
