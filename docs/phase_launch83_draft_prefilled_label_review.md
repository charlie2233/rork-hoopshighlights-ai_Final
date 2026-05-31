# Phase Launch83: Draft-Prefilled Label Review

## Scope

This pass reduces the remaining launch-grade team/highlight accuracy bottleneck by letting the local manual-review page preload GPT draft labels. It does not treat GPT as ground truth: draft rows marked `humanReviewRequired` still render as unreviewed and must be explicitly accepted by a human reviewer.

Branch under test: `codex/phase-launch70-editing-analysis-progress`.

## Change

`scripts/build_team_highlight_label_review_page.py` now accepts:

```bash
--draft-bundle /path/to/team_highlight_manual_labels_bundle_draft.json
```

Behavior:

- Validates the draft bundle schema.
- Matches draft rows by `caseId` plus `labelId` or `predictionClipId`.
- Prefills expected team, highlight, event, outcome, and notes.
- Sanitizes forbidden URL/object-key fields before embedding anything in the local page.
- Forces rows to remain unreviewed when `humanReviewRequired=true` or the bundle source is a draft.
- Displays how many clips were prefilled.

## Local Launch71 Review Page

Command:

```bash
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --draft-bundle /Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
```

Evidence:

- Draft bundle source: `gpt_draft_requires_human_review`.
- Draft cases: `3`.
- Draft clips: `66`.
- Generated review page cases: `3`.
- Generated review page cards: `66`.
- Generated review page reviewed checkbox count: `0`.
- Generated page shows `GPT draft prefilled 66 clips. Human review is still required.`
- Generated page includes `Next incomplete` and `Mark reviewed + next`.
- Generated page scan found no `X-Amz-Signature`, `uploadUrl`, `sourceObjectKey`, `sourceUrl`, `downloadUrl`, `presignedUrl`, `resultObjectKey`, `uploadHeaders`, `AKIA`, `ASIA`, or OpenAI key-looking values.
- Generated page scan found no `Approve all` or `markAllReviewed`.

The regenerated HTML remains a local ignored artifact and was not staged as source.

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

The new unit test covers the safety case where a GPT draft bundle tries to provide `needsLabel=false`; because the bundle is marked `humanReviewRequired`, the rendered review page still leaves the clip unreviewed.

## Human Next Step

Open `artifacts/team_highlight_accuracy_launch71_review.html`, use `Next incomplete`, review each prefilled clip against the source video, click `Mark reviewed + next` only after the label is correct, then download all labels. After that:

```bash
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --bundle ~/Downloads/team_highlight_manual_labels_bundle.json \
  --json
```

If the dry run is ready, apply:

```bash
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --bundle ~/Downloads/team_highlight_manual_labels_bundle.json \
  --apply \
  --json
```

Then rebuild the launch-grade accuracy report:

```bash
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --json
```
