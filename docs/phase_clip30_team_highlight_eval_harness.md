# Phase Clip30: Team Highlight Eval Harness

## Goal

Make the 85% selected-team/highlight quality target measurable before we claim it for internal TestFlight. The app can now ask which team the user wants, the cloud can quick-scan jersey colors, and uncertain clips stay reviewable. This phase adds the scoring harness that turns labeled internal footage into pass/fail metrics.

## What Was Added

- `scripts/evaluate_team_highlight_accuracy.py` scores labeled JSON exports without reading videos or calling providers.
- The evaluator measures:
  - selected-team precision for confident team attribution
  - selected-team highlight recall with uncertain clips included for Review
  - highlight precision and recall for the requested team scope
  - defensive-event recall for blocks, steals, and defensive stops
  - uncertain review count
- Default thresholds are `0.85` for selected-team precision, selected-team recall with uncertain clips, highlight precision, highlight recall, and defensive-event recall.

## Input Shape

The script accepts either a top-level `clips` list or a `cases` list:

```json
{
  "selectedTeamId": "team_dark",
  "confidenceThreshold": 0.85,
  "clips": [
    {
      "expected": {
        "teamId": "team_dark",
        "isHighlight": true,
        "eventType": "block"
      },
      "prediction": {
        "keep": true,
        "teamAttribution": {
          "teamId": "team_dark",
          "confidence": 0.94
        }
      }
    }
  ]
}
```

For uncertain but plausible clips, set `keep: true`, `includeForReview: true`, and either `teamAttributionStatus: "uncertain"` or a confidence below the case threshold. Those clips count toward recall-with-review, not confident precision.

## How To Run

```bash
python3 -m scripts.evaluate_team_highlight_accuracy path/to/labeled_eval.json --json
```

Use the default thresholds for internal beta. If an eval set is intentionally narrower, pass explicit `--min-*` thresholds in the command and record that in the launch notes.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `python3 -m unittest scripts.test_team_highlight_accuracy_eval -v` -> 4 tests passed.
- `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/test_team_highlight_accuracy_eval.py` -> passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 39 tests passed.
- `git diff --check` -> passed.

## Launch Recommendation

Do not claim 85% real-world selected-team or highlight accuracy until this harness passes on a labeled internal footage set that includes makes, misses, blocks, steals, uncertain jersey-color cases, and opponent highlights. Keep uncertain clips reviewable while collecting the set.
