# Phase Clip28: Cloud Team Quick Scan

## Goal

Move team targeting from a schema-only contract toward real cloud-owned team detection. The backend now samples video frames and candidate-clip frames, asks a vision-capable GPT model to label jersey-color teams, and attaches per-clip team attribution before selected-team filtering.

## Architecture

- Cloud analysis still owns team scanning, clip attribution, filtering, and candidate quality.
- iOS still only uploads, requests a pre-analysis scan, shows the detected color teams, sends the selected team mode/color, and shows the resulting clips.
- GPT receives sampled JPEG frames only. It never receives full video files, storage paths, upload URLs, or presigned URLs.
- GPT returns strict Structured Output JSON with detected teams and clip attributions.
- Backend filtering remains deterministic:
  - confidence `>= 0.85` and matching team/color is selected-team evidence
  - confidence `< 0.85` is uncertain
  - uncertain clips remain reviewable when `includeUncertain=true`
  - confident opponent clips are excluded
- Blocks, steals, defensive stops, and forced turnovers are explicitly attributed to the defending playmaker's team.

## Pre-Analysis Team Choice

- iOS can now prepare a cloud analysis job, upload the source once, call `POST /v1/analysis/jobs/{jobId}/team-scan`, and keep the prepared job idle while the user chooses a team.
- The Video import screen starts this team scan after import when cloud analysis is enabled.
- Detected team buttons are labeled by jersey color, with All teams always available.
- Full analysis starts later through the same prepared job and includes the user's selected `teamSelection`.
- If the scan fails or returns no clear teams, the app keeps the static All/Dark/Light fallback choices.

## Runtime Controls

- `HOOPS_TEAM_QUICK_SCAN_ENABLED`
- `HOOPS_OPENAI_API_KEY`
- `HOOPS_TEAM_QUICK_SCAN_MODEL`
- `HOOPS_TEAM_QUICK_SCAN_VIDEO_FRAME_COUNT`
- `HOOPS_TEAM_QUICK_SCAN_CLIP_FRAMES_PER_CLIP`
- `HOOPS_TEAM_QUICK_SCAN_FRAME_WIDTH`
- `HOOPS_TEAM_QUICK_SCAN_JPEG_QUALITY`
- `HOOPS_TEAM_QUICK_SCAN_MAX_IMAGE_BYTES`
- `HOOPS_TEAM_QUICK_SCAN_MIN_TEAM_CONFIDENCE`
- `HOOPS_TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS`
- `HOOPS_TEAM_QUICK_SCAN_MAX_OUTPUT_TOKENS`

If `HOOPS_TEAM_QUICK_SCAN_ENABLED` is unset, the backend follows the existing GPT editor/reranker flags. If the flag is enabled but no OpenAI key is configured, analysis falls back without team attribution, so selected-team UI must stay on All teams until real jersey-color scan results are available.

## Safety

- Request payloads use `store=false`.
- Payloads contain data URLs for sampled frames and compact clip metadata only.
- No full videos are sent to GPT.
- No FFmpeg commands from GPT are accepted or used.
- No API keys, storage credentials, source paths, or presigned URLs are included in GPT payloads.
- Low-confidence attributions are not treated as selected-team proof.

## Current Limits

The pre-analysis handshake is wired for the cloud path, but it is still a beta-quality UX: the scan reserves the existing cloud-analysis quota when the prepared job is created, and scan quality still needs a labeled footage set. If the user skips or the scan is unavailable, analysis still falls back to the existing selected-team contract and uncertain clips remain reviewable.

Do not claim 85% team-attribution accuracy yet. The code uses an 85% confidence threshold for deterministic selected-team filtering, but a real labeled evaluation set is still required before accuracy claims.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan ios.backend.tests.test_pipeline_quality -v` -> 25 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/api.py ios/backend/app/models.py ios/backend/app/config.py ios/backend/app/pipeline.py ios/backend/app/team_quick_scan.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 110 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 77 tests passed.
- XcodeBuildMCP `test_sim` with `-only-testing:HoopsClipsTests` on iPhone 17 Pro simulator -> 69 tests passed.
- XcodeBuildMCP `build_sim` for `HoopsClips` Debug on iPhone 17 Pro simulator -> passed with no warnings.
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip7-native-shot-signals-dd -quiet` -> passed.
- `git diff --check` -> passed.

## Launch Recommendation

Use this in internal staging with `includeUncertain=true`. Review uncertain clips in the app until a labeled team-attribution eval set proves the threshold. Next, collect a small labeled team-color/clip-ownership eval set from internal TestFlight footage and track selected-team precision/recall before claiming an 85% real-world accuracy number.
