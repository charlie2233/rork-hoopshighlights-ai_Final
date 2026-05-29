# Phase Clip33: Label Prediction Integrity

## Goal

Prevent stale or mismatched manual labels from silently scoring the wrong cloud-analysis prediction clip. The launch-grade team/highlight accuracy report must be built from the exact real analysis output that was labeled, not from a template whose clip indexes happen to line up after a new run.

## Change

- `scripts/build_team_highlight_eval_payload.py` now preserves `predictionIndex: 0` as a valid explicit index.
- When a label row includes both `predictionIndex` and `predictionClipId`, the builder verifies that the indexed analysis clip has the same clip ID.
- When a label row includes `predictionIndex` plus `start`/`end`, the builder verifies that the label window overlaps the indexed analysis clip enough for launch evidence.
- Mismatches raise before evaluation, so stale label templates cannot inflate selected-team precision, highlight recall, or defensive coverage.

## Why This Matters

The label template flow intentionally includes every prediction row so internal reviewers can label real makes, misses, blocks, steals, boring clips, opponent clips, uncertain team ownership, and bad timing windows. If a later analysis run reorders or replaces clips, trusting only the numeric index could attach a human label to the wrong prediction. This phase makes the evidence builder cross-check the stable clip ID and timing window before scoring.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `python3 -m unittest scripts.test_build_team_highlight_eval_payload -v` -> 8 tests passed.
- `python3 -m py_compile scripts/build_team_highlight_eval_payload.py scripts/make_team_highlight_label_template.py scripts/test_build_team_highlight_eval_payload.py` -> passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 89 tests passed.
- `git diff --check` -> passed.

## Launch Recommendation

Use a fresh manual-label template for each real cloud analysis run. If the builder reports a prediction ID or timing mismatch, regenerate the template from the current analysis output and relabel the affected rows instead of forcing the old file through.
