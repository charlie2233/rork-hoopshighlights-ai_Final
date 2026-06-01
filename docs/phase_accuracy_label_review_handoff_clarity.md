# Phase Accuracy: Label Review Handoff Clarity

## Goal

Make the human-review path for the launch-grade team/highlight accuracy report easier to follow.

## Change

- The generated `next_steps.md` now tells the reviewer to start with `Next close review`.
- It documents the fast keyboard review loop:
  - `S/E/F` jump to start/event/finish
  - `J/L` scrub back/forward 0.5 seconds
  - `K` play/pause synced angles
  - `P` copy the draft prediction
  - `1/2/3` quick label after watching
  - `R` mark reviewed and continue
- It reminds the reviewer that the page auto-saves a browser draft, but they still need to download the launch-ready bundle before closing the browser.

## Guardrails

- This only changes generated operator handoff text.
- It does not weaken the human-review requirement.
- It does not mark GPT draft labels as complete.
- It does not change app runtime, cloud analysis, rendering, upload, storage, or GPT production behavior.

## Validation

Commands:

```bash
python3 -m py_compile scripts/prepare_team_highlight_labeling_bundle.py scripts/test_prepare_team_highlight_labeling_bundle.py
python3 -m unittest scripts.test_prepare_team_highlight_labeling_bundle -v
python3 -m unittest scripts.test_prepare_team_highlight_labeling_bundle scripts.test_build_team_highlight_label_review_page scripts.test_apply_team_highlight_manual_labels scripts.test_build_launch_team_accuracy_report -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
```

Results:

- Python compile: passed.
- Focused labeling bundle tests: passed, 2 tests.
- Related label/report tests: passed, 19 tests.
- Script test discovery: passed, 141 tests.
- `git diff --check`: passed.

## Launch Note

This reduces friction in the 54-clip human review loop. The launch blocker remains until a human completes every label, applies the downloaded bundle, rebuilds the accuracy report, and reruns submission preflight with `--team-accuracy-report`.
