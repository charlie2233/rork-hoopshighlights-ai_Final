# Phase Clip50: Eval Timing Quality Gate

## Goal

Make the internal 85% accuracy proof reject tiny clips, pre-basket-only clips, and kept shots without enough event context.

## Change

- `scripts/evaluate_team_highlight_accuracy.py` now includes `clipTimingQuality` with a default `0.85` threshold.
- Kept or review-included predictions are scored for timing/context quality.
- Shot-like clips must include at least 3 seconds, setup context before `eventCenter`, and visible follow-through context after `eventCenter`.
- Defensive clips must include useful lead-in and follow-through around the defensive event.
- Explicit `nativeShotSignals.timingWindowOk: false` fails the timing-quality check.
- The eval harness docs now require `start`, `end`, and `eventCenter` in labeled prediction exports.

## Why

The product goal is not just selected-team precision/recall. The eval must also prevent us from claiming 85% quality while keeping 0.1 second clips, late pre-basket windows, or shots with no setup/outcome context.

## Architecture

- This is a metadata-only scoring harness; it does not read videos or call providers.
- Cloud analysis/editing remains responsible for producing candidate timing and native shot signals.
- The evaluator turns labeled exports into launch evidence.

## Validation

- `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/test_team_highlight_accuracy_eval.py`
  - Passed with no compiler output.
- `python3 -m unittest scripts.test_team_highlight_accuracy_eval -v`
  - Passed: 7 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Passed: 42 tests.
- `git diff --check`
  - Passed with no whitespace errors.

## Launch Recommendation

Do not claim the 85% quality target unless the labeled internal eval passes `clipTimingQuality` alongside selected-team precision, selected-team recall with uncertain review, highlight precision/recall, and defensive-event recall.
