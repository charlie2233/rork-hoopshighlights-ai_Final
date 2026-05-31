# Phase Launch87: Label Review Ready Bundle Guard

## Scope

This pass makes the local label review page harder to misuse for the launch-grade 85% team/highlight accuracy proof. It does not change cloud analysis, GPT draft labels, iOS behavior, rendering, or the accuracy thresholds.

Branch under test: `codex/phase-launch70-editing-analysis-progress`.

## Change

The review page now has two bundle paths:

- `Download launch-ready labels`: disabled until every clip is marked reviewed and has expected team, highlight, event, and outcome.
- `Download all labels`: still available for draft/partial bundle export, with the existing incomplete-label confirmation.

If the launch-ready action is triggered while labels are incomplete, the page shows the incomplete count and jumps to the next incomplete clip.

## Launch71 Evidence

Command:

```bash
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --draft-bundle /Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
```

Output summary:

- Case count: `3`.
- Clip count: `66`.
- Draft prefill applied clips: `66`.
- Draft prefill skipped clips: `0`.
- `humanReviewRequired`: `true`.

Generated page checks:

- Contains `download-ready-button`.
- Contains `downloadLaunchReadyLabels`.
- Contains the incomplete-label guard copy: `Finish every label before downloading launch-ready labels.`
- Shows `GPT draft prefilled 66 clips. Human review is still required.`
- Has 66 clip cards.
- Has 0 reviewed checkboxes checked.
- Secret/presigned URL scan found no `X-Amz-Signature`, `uploadUrl`, `sourceObjectKey`, `sourceUrl`, `downloadUrl`, `presignedUrl`, `resultObjectKey`, `uploadHeaders`, `AKIA`, `ASIA`, OpenAI key-looking values, `Approve all`, or `markAllReviewed`.

## Tests

Commands:

```bash
python3 -m py_compile \
  scripts/build_team_highlight_label_review_page.py \
  scripts/test_build_team_highlight_label_review_page.py
```

Result: pass.

```bash
python3 -m unittest scripts.test_build_team_highlight_label_review_page -v
```

Result: 3 tests passed.

## Launch Impact

This does not complete the launch accuracy blocker. It reduces the chance that a draft or incomplete label bundle is mistaken for the final launch-ready evidence before running `scripts/apply_team_highlight_manual_labels.py` and `scripts/build_launch_team_accuracy_report.py`.
