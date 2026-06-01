# Phase Accuracy: Label Review Scrub Shortcuts

## Goal

Reduce the remaining human-review bottleneck for the launch-grade selected-team/highlight accuracy report.

## Change

- The local team-highlight label review page now shows a compact shortcut strip.
- Added synced video controls:
  - `J`: scrub all source angles back 0.5 seconds
  - `K`: play or pause all synced source angles
  - `L`: scrub all source angles forward 0.5 seconds
- Existing label shortcuts remain: `S/E/F`, `P`, `R`, `N`, and `1/2/3`.

## Guardrails

- This only changes the local human-labeling helper.
- It does not mark GPT draft labels as launch-ready.
- Every clip still needs explicit human review before the 85% accuracy report can count.
- No full videos are sent to GPT, no remote URLs are embedded, and no app/cloud runtime behavior changes.

## Validation

Commands:

```bash
python3 -m py_compile scripts/build_team_highlight_label_review_page.py scripts/test_build_team_highlight_label_review_page.py
python3 -m unittest scripts.test_build_team_highlight_label_review_page -v
python3 -m unittest scripts.test_build_team_highlight_label_review_page scripts.test_prepare_team_highlight_labeling_bundle scripts.test_apply_team_highlight_manual_labels scripts.test_build_launch_team_accuracy_report -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
```

Results:

- Python compile: passed.
- Focused label review page tests: passed, 8 tests.
- Related label/report tests: passed, 19 tests.
- Script test discovery: passed, 141 tests.
- `git diff --check`: passed.

## Launch Note

This makes the evidence loop faster but does not clear the launch blocker by itself. The current labeling bundle still needs human-approved labels before rebuilding the launch accuracy report.
