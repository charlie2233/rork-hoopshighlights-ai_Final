# Phase Clip98 - Evaluator Shot Context Parity

## Goal

Keep launch accuracy evidence aligned with production EditPlan validation after tightening shot context quality.

## Change

- Updated `scripts/evaluate_team_highlight_accuracy.py` so kept or review-included shot clips need at least `1.2s` of setup before `eventCenter` and `0.8s` of outcome context after it.
- Added a regression test for borderline shot windows that would have passed the older `0.9s` / `0.6s` evaluator floor but should fail the current production quality bar.

## Why

The internal submission preflight depends on a launch-grade labeled-footage accuracy report. That report should not be able to pass using timing windows that the backend EditPlan validator would reject as too close to the basket/result.

## Guardrails

- This is evaluator-only; it does not move analysis/rendering into iOS.
- GPT is still a semantic editor only and cannot create renderer commands.
- Uncertain selected-team clips can still remain reviewable, but if they are shot clips they must carry enough visible setup and outcome context to count as timing-quality evidence.

## Validation

Run after this phase:

```bash
python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/test_team_highlight_accuracy_eval.py
python3 -m unittest scripts.test_team_highlight_accuracy_eval -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/submission_readiness_preflight.py --skip-live
git diff --check
```

## Remaining Launch Proof

This keeps the evidence gate honest, but it is still not the real 85% proof. Internal launch still needs a real labeled-footage eval report generated from the cloud path, available iPhone/TestFlight smoke, live Worker/version/kill-switch proof, Cloudflare deploy credential proof, and unblocked GitHub Actions.
