# Phase Clip34: Selected-Team Prefilter Recall

## Goal

Keep selected-team highlights from being lost before team filtering when the highest ranked native or provider candidates are mostly the other team.

## Change

- Selected-team analysis now expands the backend candidate pool before provider/native detection and normalization.
- The expanded pool is used only when `TeamSelection.mode == "team"`.
- The final review result is trimmed back to `settings.max_returned_clips` after quick scan attribution and team filtering.
- "All teams" analysis keeps the existing candidate limit.
- The selected-team prefilter multiplier is bounded so staging cannot accidentally return an unbounded review pool.

## Product Behavior

- Users can choose a detected jersey-color team before analysis.
- If the user chooses a specific team, confident opponent clips are filtered out after cloud quick scan attribution.
- Low-confidence or uncertain team clips can still remain reviewable when `includeUncertain` is enabled.
- Blocks, steals, forced turnovers, defensive stops, made shots, and missed shots remain eligible highlight outcomes; this phase only improves recall before team filtering.

## Cloud Boundary

This change stays entirely in the cloud backend analysis pipeline. iOS still only uploads/imports video, shows detected team choices, starts analysis, previews/reviews returned clips, and controls export/share. No local iOS video analysis, rendering, or composition was added.

## Validation

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios/backend/tests/test_pipeline_quality.py -v` -> 25 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 116 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 78 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 39 tests passed.
- `XcodeBuildMCP build_sim` for `HoopsClips` Debug on iPhone 17 Pro simulator -> passed. Log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-26T20-24-05-876Z_pid20749_f53e907b.log`.
- `XcodeBuildMCP test_sim` for `HoopsClips` Debug on iPhone 17 Pro simulator -> 73 passed, 0 failed, 3 skipped. Result bundle: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-05-26T20-24-17-943Z_pid20749_4ec6690d.xcresult`.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip7-native-shot-signals-dd CODE_SIGNING_ALLOWED=NO build-for-testing` -> `TEST BUILD SUCCEEDED`.
- `git diff --check` -> passed.

## CI Status

- PR #32 latest checked head before this doc update was `e04e121`.
- `Cloud Edit Deploy Preflight` run `26472899452` failed before runner execution: failed jobs had empty `steps`, and `gh run view --log-failed` returned `log not found`.
- `iOS Internal TestFlight Upload` run `26472899448` showed the same empty-step/log-missing behavior.
- GitHub staging secret names include `APP_STORE_CONNECT_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID`, `APP_STORE_CONNECT_API_KEY_BASE64`, and `CLOUDFLARE_API_TOKEN`; values were not printed.
- GCP Secret Manager still does not have `HOOPS_OPENAI_API_KEY` in project `hoopsclips-9d38f` as of 2026-05-26.

## Launch Recommendation

Run the internal labeled-footage eval with selected-team cases where:

- the first ranked candidates are the opponent team
- the selected team has later but valid plays
- defensive plays are selected-team highlights
- jersey color attribution is uncertain but still review-worthy

The 85% quality target is not proven until this real-footage eval passes.
