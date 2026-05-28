# Phase Clip76: Strict Shot Tracker Eval

## Goal

Make the internal 85% selected-team/highlight proof harder to game for made-basket clips. A kept made shot should not count as outcome-evidence quality from a provider label, a generic `Made Shot` tag, or weak rim aftermath. The evaluator should require shot-tracker-style rim-entry evidence before a made basket helps the launch accuracy claim.

## Changes

- Tightened `scripts/evaluate_team_highlight_accuracy.py` for made-shot evidence:
  - rejects `outcomeEvidenceSource=label_only`
  - rejects low `outcomeReliabilityScore` when supplied
  - requires `rimEntrySequenceConfidence >= 0.72`
  - requires approach, rim-entry, and follow-through frame roles
  - requires continuous trajectory and at least two ball-flight roles
  - requires explicit `ballPathVisible` and `rimResultVisible`
- Preserved blocked-shot and missed-shot evidence handling, while making those paths require explicit visibility booleans instead of treating missing fields as acceptable.
- Extended the real-footage eval payload builder to carry `outcomeEvidenceSource` and `outcomeReliabilityScore` from cloud analysis into the evaluator payload.
- Added regression tests for:
  - label-only made-shot evidence failing the outcome-quality metric
  - low rim-entry sequence confidence failing the outcome-quality metric

## Architecture Notes

- Cloud remains responsible for analysis, GPT selection, edit planning, rendering, storage, and quality evidence.
- This phase does not inspect video pixels locally and does not add iOS analysis/rendering/export.
- The evaluator still scores metadata exported from real cloud runs plus manual labels. It is a launch proof gate, not a replacement for GPT/CV/FFmpeg.

## Validation

Commands run from:

`/Users/hanfei/.config/superpowers/worktrees/rork-hoopshighlights-ai_Final/codex-phase-clip5-hybrid-recall-quality`

```bash
python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/build_team_highlight_eval_payload.py scripts/test_team_highlight_accuracy_eval.py
```

Result: passed with exit code 0.

```bash
python3 -m unittest scripts.test_team_highlight_accuracy_eval -v
```

Result: passed. 13 tests passed, 0 failed.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Result: passed. 55 tests passed, 0 failed.

```bash
git diff --check
```

Result: passed with exit code 0.

## Remaining Blockers

- This tightens the proof gate but does not itself prove the 85% real-footage target.
- Internal launch still needs an actual labeled-footage eval payload with selected-team makes, misses, blocks, steals, forced turnovers, uncertain review clips, opponent highlights, and bad-window negatives.
