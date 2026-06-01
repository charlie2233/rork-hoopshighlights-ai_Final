# Phase: Accuracy Label Review Quick Actions

Date: 2026-06-01
Branch: `codex/phase-accuracy-label-review-quick-actions`

## Goal

Make the real-footage selected-team/highlight labeling loop faster without weakening the launch accuracy gate. HoopClips still needs human-approved labels before claiming the 85% selected-team/highlight target.

## Changes

- Added quick-label actions to the local team-highlight review page:
  - `Selected highlight`
  - `Not highlight`
  - `Bad window`
- Added keyboard shortcuts while a clip card is focused:
  - `1`: selected-team highlight
  - `2`: not highlight
  - `3`: bad timing window
- Quick actions fill required expected fields, mark the clip reviewed, and move to the next incomplete clip.
- Each quick action writes an explicit note saying it was quick-labeled after human review.

## Safety

- This is a local labeling tool only; it does not upload, render, analyze, or export videos.
- GPT draft labels still require human review and do not count by themselves.
- The generated page still blocks launch-ready label download until every clip has team, highlight, event, outcome, and reviewed fields.
- No presigned URLs, storage object keys, credentials, or remote video URLs are added.

## Validation

- Passed: `python3 -m py_compile scripts/build_team_highlight_label_review_page.py scripts/test_build_team_highlight_label_review_page.py scripts/prepare_team_highlight_labeling_bundle.py scripts/test_prepare_team_highlight_labeling_bundle.py`
- Passed: `python3 -m unittest scripts.test_build_team_highlight_label_review_page -v` (8 tests)
- Passed: `python3 -m unittest scripts.test_prepare_team_highlight_labeling_bundle scripts.test_build_team_highlight_label_review_page scripts.test_apply_team_highlight_manual_labels scripts.test_build_launch_team_accuracy_report -v` (19 tests)
- Passed: `python3 -m unittest discover -s scripts -p 'test_*.py' -v` (139 tests)
- Passed: generated a local review page at `/tmp/hoopclips_label_quick_actions/review.html` from a one-case manifest fixture; metadata reported 1 case, 1 clip, and 1 video angle.
- Passed: `git diff --check`
- Not run: browser screenshot verification. The available Browser desktop tool requires a local action pin in this session, and Playwright is not installed in the local Node REPL.
- Not run: GitHub Actions, to preserve the current budget.

## Launch Notes

This improves the manual evidence loop for internal TestFlight readiness. The app is still not launch-ready until real labeled footage passes the accuracy gate and the installed iPhone smoke proves the cloud import, analysis, review, AI edit, render, revision, and share flow.
