# Phase Label Review Position Cue

Branch: `codex/phase-label-review-position-cue`

## Goal

Reduce the launch accuracy bottleneck by making the local human label-review page easier to use. The app still needs a launch-grade selected-team/highlight accuracy report, and the current label bundle remains incomplete until every clip is manually reviewed.

## What Changed

- Added a persistent review-position cue to the generated label page:
  - visible clip position in the current priority filter
  - current review priority
  - current clip completion state
  - overall complete/total count
- Improved restored local-draft status so reviewers immediately see how many labels are already complete after browser draft restore.
- Regenerated the local review page at `artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html` so the cue is available now.

## Architecture Notes

- This is local label-review tooling only.
- It uses cloud-generated analysis metadata and local source video playback.
- It does not run product analysis, render video, export video, upload video, or send full videos to GPT.
- GPT draft labels remain draft-only; every clip still requires human review before launch evidence counts.

## Regenerated Review Page

Command:

```bash
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --draft-bundle /Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --output artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html \
  --json
```

Result:

- Cases: 2
- Clips: 54
- GPT draft prefilled: 54
- Skipped draft clips: 1
- Human review required: true
- Review priority counts: 49 close-review, 5 standard-review

## Validation

Local validation completed on June 2, 2026 without using GitHub Actions:

```bash
python3 -m py_compile scripts/build_team_highlight_label_review_page.py scripts/test_build_team_highlight_label_review_page.py
python3 -m unittest scripts.test_build_team_highlight_label_review_page -v
python3 scripts/submission_readiness_preflight.py --skip-live --json
git diff --check
```

Results:

- Python compile: passed.
- Label review page tests: passed, 8 tests.
- Broader scripts suite: passed, 143 tests.
- Submission readiness preflight: failed as expected for launch gates, with 22 pass, 4 warn, 8 fail while this branch was still uncommitted.
- `git diff --check`: passed.

Preflight launch failures still blocking submission:

- Tracked changes were present during the branch validation run.
- Launch-grade selected-team/highlight accuracy evidence is still missing; current label bundle progress is 0/54 clips complete.
- No `.xcarchive` or `.ipa` upload artifact was found in the expected build output locations.
- A paired iPhone was detected but unavailable for install/smoke testing.
- Latest main-branch Cloud Edit Deploy Preflight and iOS Internal TestFlight Upload runs were failed/stale.
- Latest manually dispatched deploy preflight was for an older checkout.
- Installed TestFlight post-install smoke remains unproven.

## Remaining Launch Notes

- Human review is still 0/54 complete until the reviewer marks clips reviewed in the generated page and downloads the launch-ready bundle.
- After review, run `scripts/apply_team_highlight_manual_labels.py`, rebuild `team_highlight_accuracy_report.json`, then rerun submission readiness with `--team-accuracy-report`.
- Installed TestFlight smoke, current archive/upload artifact, current deploy preflight, and live staging proof are still required before Apple submission.
