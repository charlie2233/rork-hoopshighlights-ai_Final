# Phase Launch188 Accuracy Preflight Handoff

## Goal

Make the missing launch-grade team/highlight accuracy report blocker easier to act on without weakening the gate.

The internal TestFlight preflight still must fail until a real labeled-footage report proves the 85% selected-team/highlight target. This pass changes the failure copy so it points directly to the existing local labeling bundle when one is present.

## Changes

- `scripts/submission_readiness_preflight.py` now checks for the default labeling bundle:
  - `artifacts/team_highlight_labeling_bundle/bundle_metadata.json`
  - `artifacts/team_highlight_labeling_bundle/label_status.json`
  - `artifacts/team_highlight_labeling_bundle/next_steps.md`
- When `--team-accuracy-report` is missing, the failure now includes:
  - completed clip count
  - remaining clip count
  - review page path
  - label status path
  - next-steps path
- If the bundle is missing but the manifest exists, the failure prints the command to prepare the labeling bundle.
- GPT draft labels are explicitly called out as not launch evidence until a human reviews every clip and rebuilds the report.

## Current Local Evidence

The checked-in/default artifact bundle is still incomplete:

- 54 total clips
- 0 completed clips
- 54 clips remaining

This remains a blocker, but the preflight now gives the operator a direct path instead of only saying the report is missing.

## Validation

Run:

```bash
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py
python3 -m unittest scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_missing_team_accuracy_report_points_to_existing_labeling_bundle scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_missing_team_accuracy_report_points_to_manifest_when_bundle_missing scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_team_accuracy_report_is_required_for_submission_readiness -v
python3 scripts/submission_readiness_preflight.py --skip-live
git diff --check
```

## Launch Note

This does not create the missing 85% report. It makes the next required human-review step clearer and keeps the submission gate honest.
