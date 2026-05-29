# Phase Clip138: Launch Accuracy Report Builder

## Goal

Reduce manual mistakes when producing the launch-grade selected-team/highlight accuracy evidence. The submission gate requires one report with enough selected-team, all-teams, defensive, shot-outcome, opponent, negative, bad-window, and uncertain-review coverage; internal footage will usually come from several real cloud analysis runs.

## What Was Added

- Added `scripts/build_launch_team_accuracy_report.py`.
- The script reads a manifest of real analysis JSON files and their manual label files.
- Every manifest entry is passed through `scripts/build_team_highlight_eval_payload.py`, so unfilled labels, stale `predictionIndex` / `predictionClipId` pairs, and unlabeled prediction clips are rejected before scoring.
- The script combines all generated eval cases into one `team-highlight-eval-v1` payload, runs `scripts.evaluate_team_highlight_accuracy` with launch defaults, and writes:
  - `artifacts/team_highlight_eval.json`
  - `artifacts/team_highlight_accuracy_report.json`
- The generated provider handoff now includes the one-command report builder before the submission preflight command.

The builder reads metadata JSON only. It does not inspect video pixels, call providers, upload data, expose secrets, or print presigned URLs.

## Manifest Shape

```json
{
  "cases": [
    {
      "analysisResult": "game_001_analysis.json",
      "labels": "game_001_manual_labels.json"
    },
    {
      "analysisResult": "game_002_analysis.json",
      "labels": "game_002_manual_labels.json",
      "caseId": "game_002_selected_team",
      "selectedTeamId": "team_dark",
      "confidenceThreshold": 0.85
    }
  ]
}
```

Paths are resolved relative to the manifest file. Each labels file should come from the label template flow and should be filled by a human reviewer.

## How To Run

```bash
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --eval-output artifacts/team_highlight_eval.json \
  --report-output artifacts/team_highlight_accuracy_report.json \
  --json

python3 scripts/submission_readiness_preflight.py \
  --team-accuracy-report artifacts/team_highlight_accuracy_report.json
```

The builder returns a nonzero exit code when the assembled report fails launch thresholds. That is intentional: it writes the report so the team can inspect gaps, but it does not claim the 85% target until the default evaluator passes.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `python3 -m unittest scripts.test_build_launch_team_accuracy_report scripts.test_launch_provider_input_handoff -v` -> 8 tests passed.
- `python3 -m py_compile scripts/build_launch_team_accuracy_report.py scripts/test_build_launch_team_accuracy_report.py scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py` -> passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 92 tests passed.
- `git diff --check` -> passed.

## Launch Recommendation

Use this builder after the next real staging smoke analysis exports. Include at least one all-teams case plus selected-team cases with makes, misses, blocks, steals, forced turnovers, defensive stops, opponent highlights, boring negatives, bad timing windows, and uncertain-review clips.
