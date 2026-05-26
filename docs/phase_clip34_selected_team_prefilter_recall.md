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
- `git diff --check` -> passed.

## Launch Recommendation

Run the internal labeled-footage eval with selected-team cases where:

- the first ranked candidates are the opponent team
- the selected team has later but valid plays
- defensive plays are selected-team highlights
- jersey color attribution is uncertain but still review-worthy

The 85% quality target is not proven until this real-footage eval passes.
