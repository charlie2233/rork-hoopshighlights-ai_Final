# Phase Clip92 Eval Sample Size Gate

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Prevent HoopClips from claiming the 85% selected-team/highlight target from a tiny handpicked labeled set. The evaluator already measures ownership, evidence, recall, timing, shot outcome, and defensive coverage; this phase adds minimum sample-size coverage for launch-readiness use.

## Change

- Added default evaluator coverage thresholds:
  - `minCases`: 2
  - `minScoredClips`: 12
  - `minSelectedTeamHighlights`: 6
  - `minShotOutcomeEvidenceClips`: 3
  - `minOpponentHighlights`: 2
  - `minNegativeClips`: 2
  - `minBadWindowNegatives`: 2
  - `minUncertainReviewClips`: 1
- Added CLI overrides:
  - `--min-cases`
  - `--min-clips`
  - `--min-selected-team-highlights`
  - `--min-shot-outcome-evidence-clips`
  - `--min-opponent-highlights`
  - `--min-negative-clips`
  - `--min-bad-window-negatives`
  - `--min-uncertain-review-clips`
- The default evaluator now fails if a labeled payload is too small or misses hard cases, even when every scored clip is correct.
- Narrow unit fixtures can still lower these thresholds explicitly, but those runs are not launch-readiness evidence.

## Why It Matters

The user goal is not just a local passing metric; it is a believable internal beta proof that the selected-team quick scan, GPT-led editor, clip timing, shot-tracking evidence, and defensive highlight recall work together. A two-clip or single-video sample can hide opponent-team false positives, weak shot-outcome evidence, missing steals, and late pre-basket windows.

## Validation

- `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/test_team_highlight_accuracy_eval.py` passed.
- `python3 -m unittest scripts.test_team_highlight_accuracy_eval -v` passed: 19 tests after the follow-up hard-case coverage gate.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 67 tests after the follow-up hard-case coverage and submission accuracy evidence gates.
- `git diff --check` passed.

## Remaining Proof

This makes the harness stricter, but it still does not prove the 85% target. Internal launch still needs the default evaluator to pass on real labeled footage that includes selected-team makes, misses, blocks, steals, forced turnovers, uncertain review clips, opponent highlights, and bad-window negatives.
