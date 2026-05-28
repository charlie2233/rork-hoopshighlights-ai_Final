# Phase Clip62: Eval Shot Outcome And Defensive Coverage

## Goal

Tighten the selected-team launch eval so HoopClips cannot claim the 85% highlight-quality target from easy made-shot samples only. The internal labeled set must now prove selected-team defensive events, blocks, steals, and visible shot-outcome evidence for kept or review-included shot clips.

## Change

- `scripts/evaluate_team_highlight_accuracy.py` adds `shotOutcomeEvidenceQuality` with a default `0.85` threshold.
- The evaluator now also requires confident selected-team predictions to meet `selectedTeamEvidenceQuality` with sampled-frame refs, so team ownership cannot pass from confidence alone.
- Readiness coverage now requires at least two selected-team defensive events, at least one selected-team block, and at least one selected-team steal.
- Made shots require visible rim-entry evidence, ball/rim frame roles, an outcome confidence of at least `0.65`, and non-false ball/rim visibility signals.
- Blocked shots require a blocked outcome, blocked rim sequence, defensive ball-role evidence, and visible ball path.
- The evaluator still keeps uncertain selected-team clips in recall so users can review lower-confidence moments instead of silently losing them.

## Input Fields

For shot clips, prediction exports should include:

```json
{
  "outcome": "made",
  "qualitySignals": {
    "ballPathVisible": true,
    "rimResultVisible": true
  },
  "shotResultEvidence": {
    "rimResultEvidence": "made_visible",
    "outcomeConfidence": 0.9,
    "rimEntrySequence": "visible_entry",
    "ballApproachFrameRole": "rimApproach",
    "rimEntryFrameRole": "rimEntry",
    "ballBelowRimOrNetFrameRole": "belowRim"
  },
  "shotTrackingEvidence": {
    "ballVisibleFrameRoles": ["release", "rimApproach", "rimEntry", "belowRim"],
    "rimVisibleFrameRoles": ["rimApproach", "rimEntry", "belowRim"],
    "resultFrameRole": "rimEntry",
    "ballEntersRimFrameRole": "rimEntry"
  }
}
```

## Validation

- `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/test_team_highlight_accuracy_eval.py`
  - Passed with no compiler output.
- `python3 -m unittest scripts.test_team_highlight_accuracy_eval -v`
  - Passed: 10 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Passed: 46 tests.
- `git diff --check`
  - Passed with no whitespace errors.

## Launch Recommendation

Do not use a labeled set for internal launch evidence unless it includes selected-team makes, misses, blocks, steals, forced turnovers, uncertain team-attribution clips, opponent highlights, and bad-window negatives. Clips below the confidence bar should remain reviewable, but passing readiness needs the selected-team defensive and outcome-evidence metrics above threshold.
