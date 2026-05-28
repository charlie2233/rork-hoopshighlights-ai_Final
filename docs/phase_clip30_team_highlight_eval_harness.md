# Phase Clip30: Team Highlight Eval Harness

## Goal

Make the 85% selected-team/highlight quality target measurable before we claim it for internal TestFlight. The app can now ask which team the user wants, the cloud can quick-scan jersey colors, and uncertain clips stay reviewable. This phase adds the scoring harness that turns labeled internal footage into pass/fail metrics.

## What Was Added

- `scripts/evaluate_team_highlight_accuracy.py` scores labeled JSON exports without reading videos or calling providers.
- The evaluator measures:
  - selected-team precision for confident team attribution
  - selected-team evidence quality for confident team attribution
  - selected-team highlight recall with uncertain clips included for Review
  - highlight precision and recall for the requested team scope
  - defensive-event recall for blocks, steals, forced turnovers, and defensive stops
  - clip timing/context quality for kept or review-included clips
  - shot-outcome evidence quality for made, missed, and blocked shot clips
  - minimum labeled-footage sample size
  - minimum hard-case coverage for opponent highlights, negative clips, bad-window negatives, and uncertain review clips
  - minimum selected-team defensive coverage, including at least one block and one steal
  - uncertain review count
- Default thresholds are `0.85` for selected-team precision, selected-team evidence quality, selected-team recall with uncertain clips, highlight precision, highlight recall, defensive-event recall, clip timing/context quality, and shot-outcome evidence quality. Default coverage also requires at least two cases, 12 scored clips, six selected-team highlights, three shot-outcome evidence clips, two opponent highlights, two negative clips, two bad-window negatives, one uncertain review clip, and two selected-team defensive events with at least one block and one steal.

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
        "eventType": "forced turnover"
      },
      "prediction": {
        "keep": true,
        "start": 10.0,
        "end": 14.0,
        "eventCenter": 12.0,
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

For selected-team evidence quality, confident selected-team predictions should include at least two unique `teamAttribution.evidenceFrameRefs` values and two unique `teamAttribution.evidenceRoleGroups` values. These are sampled-frame IDs and phase labels from the cloud quick scan, not images or URLs. When a prediction includes `teamEvidence`, the evaluator also treats `teamEvidence.status`, `teamEvidence.evidenceBacked`, `teamEvidence.frameRefCount`, and `teamEvidence.roleGroupCount` as authoritative summary checks, so `weak_evidence` cannot pass as confident selected-team proof.

For timing quality, include `start`, `end`, and `eventCenter` for every kept or review-included prediction. The evaluator fails tiny clips, shot clips without enough setup/outcome context, defensive clips without useful event context, and clips whose `nativeShotSignals.timingWindowOk` is explicitly false.

For shot-outcome evidence, kept or review-included shot clips should include a normalized `outcome`, `shotResultEvidence`, `shotTrackingEvidence`, and `qualitySignals`. Made shots must show visible rim entry and follow-through, blocked shots must show defensive ball disruption, and low-confidence or unclear outcome evidence fails the readiness gate.

## How To Run

```bash
python3 -m scripts.evaluate_team_highlight_accuracy path/to/labeled_eval.json --json
```

Use the default thresholds for internal beta. If an eval set is intentionally narrower for a unit test or targeted investigation, pass explicit `--min-*` thresholds in the command and record that the result is not launch-readiness evidence.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `python3 -m unittest scripts.test_team_highlight_accuracy_eval -v` -> 19 tests passed after the sample-size, hard-case coverage, and evidence-summary gates.
- `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/test_team_highlight_accuracy_eval.py` -> passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 63 tests passed after the sample-size, hard-case coverage, and team evidence-quality gates.
- `git diff --check` -> passed.

## Launch Recommendation

Do not claim 85% real-world selected-team or highlight accuracy until this harness passes on a labeled internal footage set that includes makes, misses, blocks, steals, forced turnovers, uncertain jersey-color cases, opponent highlights, bad shot-outcome evidence, and bad-window negatives such as tiny clips and pre-basket-only clips. Keep uncertain clips reviewable while collecting the set.
