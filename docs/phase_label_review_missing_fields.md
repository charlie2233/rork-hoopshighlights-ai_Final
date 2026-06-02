# Phase Label Review Missing Fields

Branch: `codex/phase-label-review-next-incomplete`

## Goal

Move the launch accuracy evidence blocker forward by making the local human label-review page easier and safer to complete. The current bundle is still 0/54 human-reviewed clips, and GPT draft labels must remain draft-only until every clip is manually checked.

## What Changed

- Added a visible per-card `Needs:` row to the generated review page.
- The row updates live as the reviewer fills fields.
- GPT-prefilled rows now clearly show that they still need `reviewed` before launch-ready download.
- If the reviewer taps `Mark reviewed + next` too early, the page reports the exact missing fields and focuses the first missing control.
- Kept the launch-ready download gate: incomplete clips still cannot use the launch-ready download button.

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

## Architecture Notes

- This is local label-review tooling only.
- It does not analyze, render, export, upload, or send video to GPT.
- It does not weaken the human-review requirement.
- It does not stage or depend on unrelated root Xcode project folders.

## Validation

Local validation completed on June 2, 2026 without using GitHub Actions:

```bash
python3 -m py_compile scripts/build_team_highlight_label_review_page.py scripts/test_build_team_highlight_label_review_page.py
python3 -m unittest scripts.test_build_team_highlight_label_review_page -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/submission_readiness_preflight.py --skip-live --json
git diff --check
```

Results:

- Python compile: passed.
- Focused label-review tests: passed, 8 tests.
- Broader scripts suite: passed, 143 tests.
- Regenerated artifact check: `missing-fields`, `Needs: reviewed`, `missingFieldsFromCard`, and `focusFirstMissingField` are present in `artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html`.
- `git diff --check`: passed.
- Submission readiness preflight: failed as expected for launch gates, with 22 pass, 4 warn, 8 fail while this branch was still uncommitted.

Preflight launch failures still blocking submission:

- Tracked changes were present during branch validation.
- Launch-grade selected-team/highlight accuracy evidence is still missing; current label bundle progress is 0/54 clips complete.
- No `.xcarchive` or `.ipa` upload artifact was found in expected build output locations.
- A paired iPhone was detected but unavailable for install/smoke testing.
- Latest main-branch Cloud Edit Deploy Preflight and iOS Internal TestFlight Upload runs were failed/stale.
- Latest manually dispatched deploy preflight was for an older checkout.
- Installed TestFlight post-install smoke remains unproven.

## Remaining Launch Notes

- Human label review is still required for all 54 clips.
- After review, apply the downloaded bundle without `--allow-incomplete`, rebuild `artifacts/team_highlight_accuracy_report.json`, and rerun submission readiness with `--team-accuracy-report`.
- Installed TestFlight smoke, a current archive/upload artifact, current deploy preflight, live staging proof, and a real-device import/render smoke are still required before Apple submission.
