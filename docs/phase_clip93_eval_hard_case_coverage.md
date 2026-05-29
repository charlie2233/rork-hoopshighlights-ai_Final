# Phase Clip93 Eval Hard Case Coverage

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Make the default 85% selected-team eval require the hard cases that matter for real launch quality, not just enough total clips. HoopClips should prove it rejects opponent-team highlights, keeps uncertain selected-team clips available for review, and includes bad-window negatives such as tiny clips and pre-basket-only clips.

## Change

- Added default evaluator coverage thresholds:
  - `minOpponentHighlights`: 2
  - `minNegativeClips`: 2
  - `minBadWindowNegatives`: 2
  - `minUncertainReviewClips`: 1
- Added CLI overrides:
  - `--min-opponent-highlights`
  - `--min-negative-clips`
  - `--min-bad-window-negatives`
  - `--min-uncertain-review-clips`
- Added metrics:
  - `opponentHighlightCount`
  - `negativeClipCount`
  - `badWindowNegativeCount`
- The default passing fixture now includes opponent highlights, uncertain review clips, and bad-window negatives.

## Guardrails

- This is still metadata-only evaluation. It does not inspect videos, send full videos to GPT, render, or expose storage URLs.
- Small test fixtures can lower these thresholds explicitly, but those runs are not launch-readiness proof.

## Validation

- `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/build_team_highlight_eval_payload.py scripts/test_team_highlight_accuracy_eval.py scripts/test_build_team_highlight_eval_payload.py` passed.
- `python3 -m unittest scripts.test_team_highlight_accuracy_eval -v` passed: 19 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 67 tests after the submission accuracy evidence gate was added.
- `git diff --check` passed.

## Remaining Proof

This makes the harness harder to game, but it still does not prove the 85% target. Internal launch still needs the default evaluator to pass on real labeled footage from the cloud path and an installed TestFlight smoke.
