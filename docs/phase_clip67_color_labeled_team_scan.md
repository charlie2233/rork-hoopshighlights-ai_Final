# Phase Clip67: Color-Labeled Team Scan Guard

## Goal

Tighten the pre-analysis team chooser so GPT Team Quick Scan can only expose selectable teams that resolve to visible jersey colors. The user should choose between color-labeled teams like `Black jerseys` or `White jerseys`, not ambiguous GPT names like `Home team` or `Away team`.

## Change

- Added backend jersey-color normalization for Team Quick Scan output.
- Accepted colors and common aliases include black/dark, white/light, blue/navy/teal, red/maroon, yellow/gold, green, orange, purple, gray/grey, and pink.
- Detected team options without a resolvable jersey color are not exposed as selectable teams.
- Ambiguous GPT labels such as `Home team` are rewritten to color labels when a color is present.
- Raw GPT aliases such as `home` and `away` are still mapped back to the normalized color team for clip attribution, so useful ownership evidence is preserved.
- Clip attributions that cannot be mapped to a detected color team still remain capped below the confident threshold and can stay reviewable as uncertain evidence.

## Architecture

- Cloud backend still owns team scan, attribution, validation, and analysis gating.
- iOS remains the control surface: upload/import, scan status, team selection, review, export, preview, download, and share.
- GPT still receives sampled keyframes and compact metadata only.
- No full videos, presigned URLs, storage keys, or renderer commands are sent to GPT.

## Validation

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_detected_team_options_are_normalized_to_jersey_colors -v
# Result: 1 test passed

PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v
# Result: 22 tests passed

PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
# Result: 154 tests passed

python3 -m unittest discover -s scripts -p 'test_*.py' -v
# Result: 49 tests passed

PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
# Result: 93 tests passed

npm --prefix services/control-plane run typecheck
# Result: passed

git diff --check
# Result: passed
```

## Launch Note

This improves the quality of the team-choice contract, but it is not an 85% real-footage accuracy proof. The labeled evaluation set still needs to pass across selected-team ownership, uncertain review clips, made/missed outcomes, blocks, steals, forced turnovers, and bad-window negatives before making the accuracy claim or treating TestFlight submission as ready.
