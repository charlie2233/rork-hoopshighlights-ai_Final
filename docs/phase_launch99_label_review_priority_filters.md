# Phase Launch99: Label Review Priority Filters

Date: 2026-05-31
Branch: `codex/phase-launch70-editing-analysis-progress`

## Scope

Reduce the manual Launch71 team-highlight label-review bottleneck without weakening the human-review requirement.

This phase only changes the local review-page generator. It does not analyze, render, export, upload, or call GPT from iOS.

## Change

The generated label-review page now shows review-priority counters and filters in the summary panel:

- All clips
- Close review
- Standard review
- Quick check

Filtering hides non-matching cards and keeps `Next incomplete`, `Next close review`, and `Mark reviewed + next` working against the visible set. There is still no bulk approve or auto-review path.

## Why

The current Launch71 draft has `66` prefilled clips, but `0` are complete for launch evidence because every clip still needs explicit review. The priority filters let the operator clear close-review clips first, then standard clips, while still requiring clip-by-clip confirmation before the launch-ready bundle can download.

## Validation

Commands:

```bash
python3 -m py_compile scripts/build_team_highlight_label_review_page.py scripts/test_build_team_highlight_label_review_page.py
python3 -m unittest scripts.test_build_team_highlight_label_review_page -v
python3 -m unittest scripts.test_build_team_highlight_label_review_page scripts.test_draft_team_highlight_manual_labels_with_gpt scripts.test_apply_team_highlight_manual_labels scripts.test_build_launch_team_accuracy_report -v
git diff --check
```

The label-status check still reports `0 / 66` complete and missing `needsLabel=false` for all clips. That is expected until a human reviewer marks the labels complete.

## Launch Impact

This improves operator throughput for the accuracy gate, but it does not clear the submission blocker. A launch-grade `--team-accuracy-report` still requires completed manual labels from real footage.
