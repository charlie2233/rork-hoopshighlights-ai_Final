# Phase Launch97 Label Review Priority Queue

Date: 2026-05-31
Branch: `codex/phase-launch70-editing-analysis-progress`

## Goal

Reduce the remaining launch-grade team/highlight accuracy bottleneck without weakening the human-review requirement.

The Launch71 review page now labels each clip as one of:

- `Close review`: uncertainty, weak confidence, unclear outcome/team, or risky evidence.
- `Quick check`: high-confidence complete draft labels that still need human verification.
- `Standard review`: normal manual review.

This is only a reviewer aid. It does not mark clips reviewed, does not bulk approve labels, and does not let GPT count as launch evidence.

## Change

- `scripts/build_team_highlight_label_review_page.py`
  - Adds `reviewPriority` metadata to each review clip.
  - Renders a compact priority badge on each clip card.
  - Adds a `Next close review` control to jump to the next incomplete high-risk clip.
  - Keeps `needsLabel=true` for GPT draft-prefilled labels when `humanReviewRequired=true`.
- `scripts/test_build_team_highlight_label_review_page.py`
  - Covers close-review and quick-check classification.
  - Covers the new button and rendered priority metadata.

## Regenerated Local Review Page

Command:

```bash
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --draft-bundle /Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
```

Result:

- Cases: `3`
- Clips: `66`
- GPT draft prefilled clips: `66`
- Skipped draft clips: `0`
- Human review required: `true`
- Priority queue from `--json` output:
  - `needs_close_review`: `58`
  - `standard_review`: `8`

Sensitive storage strings checked absent from the generated page:

- `sourceObjectKey`
- `X-Amz-Signature`
- `uploadUrl`
- `downloadUrl`
- `presignedUrl`

## Validation

```bash
python3 -m py_compile \
  scripts/build_team_highlight_label_review_page.py \
  scripts/test_build_team_highlight_label_review_page.py
```

Result: passed.

```bash
python3 -m unittest scripts.test_build_team_highlight_label_review_page -v
```

Result: `4` tests passed.

The in-app Browser was attempted against the generated local `file://` review page, but Browser policy rejected that URL. No alternate browser workaround was used. The CLI `--json` output now reports `reviewPriorityCounts` so this review queue can be verified without opening the local page in Browser.

## Launch Notes

The accuracy gate is still not complete. The operator still needs to open `artifacts/team_highlight_accuracy_launch71_review.html`, verify each clip against the source video, mark every row reviewed, download `team_highlight_manual_labels_bundle.json`, apply it without `--allow-incomplete`, and generate the launch-grade accuracy report.
