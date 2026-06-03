# Phase Label Review Close First

## Goal

Move the human-reviewed accuracy blocker forward by making the launch label-review flow point reviewers at uncertain clips first.

## Finding

The current submission preflight still fails because the launch-grade team/highlight accuracy report is missing. The local bundle is `0/54` human-reviewed clips, with GPT draft labels prefilled for speed but not launch evidence. The review priority queue currently has 49 close-review clips and 5 standard-review clips.

## Change

- The generated label review page now shows a visible `Review order` cue:
  - Close review clips first
  - Standard review next
  - Quick checks last
- The main action row now puts `Next close review` before `Next incomplete`.
- `next_steps.md` generation now explains that close-review clips have uncertainty or weak evidence, and that quick checks still require watching the video before marking reviewed.

## Architecture

- This changes only the local human label-review helper.
- It does not mark any clip human-reviewed.
- It does not run product analysis, render video, upload video, call GPT, or move any launch-gated backend work onto iOS.
- GPT draft labels still do not count until every clip is human-reviewed and the launch report is rebuilt.

## Validation

Passed:

```bash
python3 -m py_compile scripts/build_team_highlight_label_review_page.py scripts/prepare_team_highlight_labeling_bundle.py scripts/test_build_team_highlight_label_review_page.py scripts/test_prepare_team_highlight_labeling_bundle.py
python3 -m unittest scripts.test_build_team_highlight_label_review_page scripts.test_prepare_team_highlight_labeling_bundle -v
```

Also passed:

```bash
python3 -m unittest scripts.test_build_team_highlight_label_review_page scripts.test_prepare_team_highlight_labeling_bundle scripts.test_apply_team_highlight_manual_labels scripts.test_build_launch_team_accuracy_report scripts.test_submission_readiness_preflight -v
```

Final hygiene passed:

```bash
git diff --check
```

## Launch Note

This reduces the chance that the human reviewer spends time on easier clips before the uncertain ones, but it does not clear the label gate. The launch report is still blocked until all 54 clips are human-reviewed and applied without `--allow-incomplete`.
