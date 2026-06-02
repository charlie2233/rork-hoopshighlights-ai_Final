# Phase: Accuracy Label Bundle Staleness Preflight

## Goal

Make the launch readiness preflight more useful for the remaining team-highlight accuracy blocker. The app still needs a human-reviewed launch-grade accuracy report before submission, and GPT draft labels remain review aids only.

## Change

- `scripts/submission_readiness_preflight.py` now reports GPT draft prefill counts from the local labeling bundle metadata.
- It also reports review priority counts, such as close-review clips vs standard-review clips.
- If the generated review page or `next_steps.md` is missing current fast-review affordances, preflight tells the operator to regenerate the bundle before human review.
- When the existing bundle metadata points at a GPT draft bundle, the regeneration command preserves it with `--draft-bundle`.
- The stale-bundle hint checks for:
  - `Next close review`
  - `J/L` scrub shortcut copy
  - synced scrub controls
  - launch-ready label export guard copy
  - updated next-step handoff instructions

## Evidence

Current local preflight found the expected launch blocker and now gives a sharper action:

```text
Existing labeling bundle progress: 0/54 clips complete, 54 remaining.
GPT draft prefilled 54 clip(s) and skipped 1; review priority queue: 49 close-review, 5 standard-review.
Labeling bundle looks stale or incomplete ... Regenerate before review with:
python3 scripts/prepare_team_highlight_labeling_bundle.py --manifest artifacts/team_highlight_accuracy_manifest.json --video-path /absolute/path/to/source.mp4 --output-dir artifacts/team_highlight_labeling_bundle --draft-bundle <existing-draft-bundle>
```

The local ignored review artifact was then regenerated successfully from current scripts with the local source video and existing GPT draft bundle:

```text
caseCount=2
clipCount=54
completeClipCount=0
incompleteClipCount=54
draftPrefill.appliedClipCount=54
reviewPriorityCounts.needs_close_review=49
reviewPriorityCounts.standard_review=5
```

## Validation

```bash
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py
python3 -m unittest scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_missing_team_accuracy_report_points_to_existing_labeling_bundle scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_missing_team_accuracy_report_warns_when_labeling_bundle_is_stale -v
python3 -m unittest scripts.test_submission_readiness_preflight -v
python3 -m unittest discover scripts -v
python3 scripts/submission_readiness_preflight.py --json
```

The preflight still fails overall, as intended, until the launch-grade human-reviewed accuracy report, archive/upload proof, available iPhone smoke, current deploy proof, and green required Actions are present.

## Launch Recommendation

Regenerate `artifacts/team_highlight_labeling_bundle` from current scripts before the next human review pass, then review all 54 clips and rebuild the launch accuracy report. Do not count GPT draft labels as launch evidence until every clip is human-reviewed.
