# Phase Clip27: Team-Targeted Highlights

## Goal

Let a user choose which team HoopClips should build highlights for before cloud analysis, while keeping cloud ownership of scanning, attribution, GPT editing, edit planning, rendering, and storage.

## Architecture

- iOS is the control surface. It lets the user choose `All teams`, `Dark jerseys`, or `Light jerseys` before analysis and sends that structured `teamSelection` with cloud analysis and cloud edit requests.
- The backend owns team targeting. Analysis jobs persist `teamSelection`, analysis results can return `detectedTeams`, and clips can carry `teamAttribution`.
- Edit planning filters confident opponent clips deterministically before ranking, GPT reranking, and plan generation.
- Uncertain clips stay in the candidate pool by default because the user can review them. The default confidence threshold is `0.85`.
- Blocks, steals, defensive stops, and forced turnovers remain eligible highlights when attributed to the selected team or uncertain.

## Schema

`teamSelection`

```json
{
  "mode": "team",
  "teamId": "team_dark",
  "label": "Dark jerseys",
  "colorLabel": "black",
  "confidenceThreshold": 0.85,
  "includeUncertain": true
}
```

`teamAttribution`

```json
{
  "teamId": "team_dark",
  "label": "Dark jerseys",
  "colorLabel": "black",
  "confidence": 0.91,
  "source": "quick_scan"
}
```

## Filtering Rules

- `mode=all`: do not filter by team.
- `mode=team`: keep clips that match `teamId` or `colorLabel` at or above `confidenceThreshold`.
- Keep uncertain clips when `includeUncertain=true`.
- Exclude only confident opponent clips.
- Never infer team ownership from iOS local video analysis.

## GPT Context

The GPT reranker now receives:

- `teamTargeting`
- per-clip `teamAttribution`
- per-clip `teamAttributionStatus`

The prompt tells GPT to select highlights for the selected team, exclude confident opponent clips, keep uncertain clips for review, and treat blocks/steals as valid highlights. The backend still validates all output and GPT still cannot generate FFmpeg commands or exact timestamps.

## iOS UX

The import/analyze screen now has a `Highlight Team` selector before analysis starts. It stores the choice in `AnalysisSettings`, sends it with cloud analysis, and sends the same selection plus clip attribution into cloud AI Edit.

## Current Limits

This phase wires the contract, deterministic filtering, GPT context, and iOS control. The current native pipeline does not yet provide a high-confidence CV/GPT team scanner for every uploaded game. When the backend/provider cannot confidently attribute team ownership, clips remain uncertain and reviewable.

## Validation Evidence

Commands run on branch `codex/phase-clip27-team-targeted-highlights`:

- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios/backend/tests/test_edit_plan_agent.py -v` -> 65 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services/editing/tests/test_gpt_reranker.py -v` -> 37 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 105 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 77 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 35 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/models.py ios/backend/app/job_store.py ios/backend/app/pipeline.py ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py` -> passed.
- `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17' -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudAnalysisRequestEncodesPreAnalysisTeamChoice -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestEncodesOptionalUserPrompt` -> test succeeded.
- `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -skip-testing:HoopsClipsUITests -skip-testing:HoopsClipsUITestsLaunchTests -quiet` -> unit tests passed after fixing backward-compatible decode for analysis results without team fields.
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -quiet` -> passed.
- `git diff --check` -> passed.

## Launch Recommendation

Keep `includeUncertain=true` for internal TestFlight. Do not claim 85% team-attribution accuracy until a real team scanner evaluation set proves it. The next quality phase should add a cloud quick-scan provider that samples frames, labels jersey colors, and produces calibrated team attribution confidence before full highlight selection.
