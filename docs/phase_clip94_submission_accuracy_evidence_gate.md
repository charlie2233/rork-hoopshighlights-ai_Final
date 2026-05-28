# Phase Clip94 Submission Accuracy Evidence Gate

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Prevent HoopClips internal submission readiness from treating small, relaxed, or handpicked eval runs as proof of the requested 85% selected-team/highlight quality target.

The app can already ask which team the user wants, preserve uncertain clips for Review, and include blocks/steals in the candidate pool. This phase makes the submission preflight require a launch-grade JSON report from the labeled-footage evaluator before the app can be called ready.

## Change

- Added `--team-accuracy-report` to `scripts/submission_readiness_preflight.py`.
- The report must come from:

```bash
python3 -m scripts.evaluate_team_highlight_accuracy artifacts/team_highlight_eval.json --json > artifacts/team_highlight_accuracy_report.json
```

- The submission preflight now fails when the report is missing, unreadable, not passing, missing evaluator metrics, or generated with thresholds below the launch defaults.
- The preflight independently checks the hard-case metrics from the report:
  - opponent highlights
  - negative clips
  - bad-window negatives such as tiny clips and pre-basket-only clips
  - uncertain review clips
  - selected-team defensive events, including at least one block and one steal

## Why It Matters

Targeted eval fixtures are useful for unit tests, but they are not launch evidence. Internal launch still needs real labeled footage from the cloud path and must prove quality on hard basketball cases, not only easy made-shot clips.

## Operator Flow

1. Build the labeled payload from real cloud analysis output and manual labels.
2. Run the evaluator with default thresholds.
3. Pass the generated report into submission readiness:

```bash
python3 scripts/submission_readiness_preflight.py --team-accuracy-report artifacts/team_highlight_accuracy_report.json
```

## Guardrails

- The preflight reads only local JSON evidence.
- It does not inspect videos, call providers, render, or upload.
- It does not print secrets, R2 credentials, storage object keys, or presigned URLs.
- Lowering evaluator thresholds remains allowed for focused debugging, but those reports fail submission readiness.

## Validation

- `python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py` passed.
- `python3 -m unittest scripts.test_submission_readiness_preflight -v` passed: 20 tests.

## Remaining Proof

This closes a readiness tooling gap; it still does not prove the 85% real-world target. The missing proof is a real labeled internal-footage report generated from the cloud path and passing the default evaluator, plus installed TestFlight smoke and live cloud render/revision/share proof.
