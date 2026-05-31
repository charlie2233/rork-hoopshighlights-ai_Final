# Phase Launch89: Label Review Keyboard Shortcuts

Date: 2026-05-30
Branch: `codex/phase-launch70-editing-analysis-progress`

## Scope

Reduce the time needed to finish the real-footage team-highlight label review that gates the 85% selected-team/highlight quality proof.

This phase only changes the local manual-review HTML generator. It does not analyze, render, export, upload, or call GPT from iOS.

## Change

The generated label review page now attaches clip timing metadata to each card and supports keyboard shortcuts when focus is on the page or a clip card:

- `s`: jump the source video to clip start.
- `e`: jump the source video to the event-center frame.
- `f`: jump the source video to clip finish.
- `r`: mark the focused clip reviewed and advance to the next incomplete clip, using the existing completion guard.
- `n`: focus the next incomplete clip.

Shortcut handling deliberately ignores `input`, `select`, and `textarea` targets so editing labels cannot accidentally seek or mark a clip.

## Validation

Commands run:

```bash
python3 -m py_compile scripts/build_team_highlight_label_review_page.py scripts/test_build_team_highlight_label_review_page.py
python3 -m unittest scripts.test_build_team_highlight_label_review_page -v
python3 -m unittest scripts.test_build_team_highlight_label_review_page scripts.test_draft_team_highlight_manual_labels_with_gpt scripts.test_apply_team_highlight_manual_labels scripts.test_build_launch_team_accuracy_report -v
git diff --check
```

Expected value:

- Human reviewer can keep the sticky video visible, use the existing jump buttons, or use keyboard shortcuts against the focused clip.
- Completion guard still blocks launch-ready bundle download until every clip has expected team, highlight, event, outcome, and reviewed state.

## Launch Blocker Impact

This does not clear the accuracy blocker by itself. It makes the remaining human review loop faster so a launch-grade label bundle can be completed and fed into:

```bash
python3 scripts/apply_team_highlight_manual_labels.py ...
python3 scripts/build_launch_team_accuracy_report.py ...
python3 scripts/submission_readiness_preflight.py --team-accuracy-report ...
```
