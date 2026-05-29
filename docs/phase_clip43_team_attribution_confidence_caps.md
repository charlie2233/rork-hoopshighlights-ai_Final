# Phase Clip43: Team Attribution Confidence Caps

## Goal

Avoid treating GPT team guesses as selected-team proof when the team identity itself is not confidently detected.

## Change

- Per-clip team attribution confidence is now capped by the matching detected team confidence.
- If a clip attribution references a team/color/label that was not detected in the `teams` list, its confidence is capped below the confident selected-team threshold.
- The clip attribution metadata is still preserved so uncertain clips remain visible for user Review when `includeUncertain` is enabled.

## Why

The user-facing target is high selected-team accuracy, not just aggressive filtering. A high-confidence per-clip label can be wrong if the broader jersey-color team identity was uncertain or missing. Capping the clip confidence keeps those clips reviewable instead of silently treating them as selected-team proof.

## Safety

- GPT still receives sampled keyframes and compact metadata only.
- No full videos, presigned URLs, storage keys, file paths, or FFmpeg instructions are sent to GPT.
- iOS behavior is unchanged; this is backend validation around GPT output.

## Validation

Run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_clip_attribution_is_capped_by_detected_team_confidence ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_clip_attribution_without_detected_team_stays_uncertain ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_payload_uses_sampled_frames_not_full_video_and_applies_attribution -v` -> 3 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/team_quick_scan.py ios/backend/tests/test_team_quick_scan.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 128 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 85 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 40 tests passed.
- `git diff --check` -> passed.
- `git diff --cached --check` -> passed.

## Launch Recommendation

Keep this cap enabled for internal beta. Labeled footage should measure selected-team precision, selected-team recall with uncertain review clips, and cases where only one jersey color is confidently detected.
