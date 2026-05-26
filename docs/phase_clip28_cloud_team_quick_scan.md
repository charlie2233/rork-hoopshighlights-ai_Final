# Phase Clip28: Cloud Team Quick Scan

## Goal

Move team targeting from a schema-only contract toward real cloud-owned team detection. The backend now samples video frames and candidate-clip frames, asks a vision-capable GPT model to label jersey-color teams, and attaches per-clip team attribution before selected-team filtering.

## Architecture

- Cloud analysis still owns team scanning, clip attribution, filtering, and candidate quality.
- iOS still only sends the selected team mode/color and shows the resulting clips.
- GPT receives sampled JPEG frames only. It never receives full video files, storage paths, upload URLs, or presigned URLs.
- GPT returns strict Structured Output JSON with detected teams and clip attributions.
- Backend filtering remains deterministic:
  - confidence `>= 0.85` and matching team/color is selected-team evidence
  - confidence `< 0.85` is uncertain
  - uncertain clips remain reviewable when `includeUncertain=true`
  - confident opponent clips are excluded
- Blocks, steals, defensive stops, and forced turnovers are explicitly attributed to the defending playmaker's team.

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

If `HOOPS_TEAM_QUICK_SCAN_ENABLED` is unset, the backend follows the existing GPT editor/reranker flags. If the flag is enabled but no OpenAI key is configured, analysis falls back safely without team attribution.

## Safety

- Request payloads use `store=false`.
- Payloads contain data URLs for sampled frames and compact clip metadata only.
- No full videos are sent to GPT.
- No FFmpeg commands from GPT are accepted or used.
- No API keys, storage credentials, source paths, or presigned URLs are included in GPT payloads.
- Low-confidence attributions are not treated as selected-team proof.

## Current Limits

This phase runs the quick scan inside cloud analysis after candidate generation, then filters the selected team. It does not yet add a separate pre-analysis iOS pause where the app uploads once, cloud scans teams, asks the user to choose from detected colors, and then starts full analysis. That is the next UX/backend handshake needed to fully satisfy "quick scan first when imported."

Do not claim 85% team-attribution accuracy yet. The code uses an 85% confidence threshold for deterministic selected-team filtering, but a real labeled evaluation set is still required before accuracy claims.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios/backend/tests/test_team_quick_scan.py ios/backend/tests/test_pipeline_quality.py -v` -> 24 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/config.py ios/backend/app/models.py ios/backend/app/pipeline.py ios/backend/app/team_quick_scan.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 109 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 77 tests passed.
- `git diff --check` -> passed.

## Launch Recommendation

Use this in internal staging with `includeUncertain=true`. Review uncertain clips in the app until a labeled team-attribution eval set proves the threshold. The next phase should add the upload -> quick scan -> user chooses detected color -> full analysis flow so the UI can offer actual detected team colors before the main analysis job runs.
