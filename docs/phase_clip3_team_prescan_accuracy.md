# Phase Clip3 Team Prescan Accuracy

## Goal

Improve the app-visible team picker and GPT-led selected-team editing quality without moving analysis, rendering, or edit planning into iOS.

## Changes

- Raised the interactive team prescan from 20 to 64 candidate clips.
- Raised rich prescan candidates from 12 to 32.
- Raised prescan frames per rich candidate from 5 to 6.
- Raised the prescan clip-frame ceiling from 96 to 288 so the budget is actually consumed as 32 rich candidates plus 32 compact tail candidates.
- Raised the prescan timeout floor from 75s to 90s.
- Expanded defensive team-scan taxonomy so clips labeled takeaway, interception, pickpocket, poke, rip, deflection, charge, loose-ball recovery, swat, and rejection receive defensive sampling and evidence validation.
- Updated GPT underfill checks to ignore review-only uncertain selected-team clips, because those clips are intentionally available for Review but should not inflate automatic render expectations.

## Architecture Notes

- Cloud backend still owns team scan, attribution, candidate filtering, GPT selection, edit planning, rendering, storage, and safety validation.
- iOS remains the control surface for import, team choice, Review, Export, preview, download, and share.
- GPT still receives sampled keyframes and compact metadata only; no full videos, source URLs, storage keys, presigned URLs, or FFmpeg commands are sent.
- Blocks, steals, deflections, turnovers, charges, and loose-ball plays are valid selected-team highlight candidates when the team evidence is strong enough.
- Uncertain selected-team clips stay visible for user review but are not treated as automatic render material unless the user keeps them.

## Validation

- `git diff --check` -> passed.
- `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests -v` -> 42 tests passed.
- `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests -v` -> 77 tests passed.
- `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_team_scan_endpoint_uses_editing_secret_and_redacts_source_details -v` -> 1 test passed.
- `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v` -> 51 tests passed.
- `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v` -> 136 tests passed.

## Launch Recommendation

Use the larger prescan in internal TestFlight, then run a real-device selected-team smoke with footage containing makes, misses, blocks, steals, deflections, loose balls, and opponent highlights. Do not claim the 85% target until the labeled eval set passes on real footage.
