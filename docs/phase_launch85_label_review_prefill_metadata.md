# Phase Launch85: Label Review Prefill Metadata

## Scope

This pass makes the local team/highlight label review generator report prefill evidence directly in its `--json` output. It is a metadata/operability change only; it does not alter cloud analysis, GPT labels, rendering, iOS behavior, or launch thresholds.

Branch under test: `codex/phase-launch70-editing-analysis-progress`.

## Change

`scripts/build_team_highlight_label_review_page.py --json` now reports:

- `caseCount`
- `clipCount`
- `draftPrefill.appliedClipCount`
- `draftPrefill.skippedClipCount`
- `draftPrefill.humanReviewRequired`
- output path

This gives the operator a machine-readable proof that the GPT draft was actually preloaded into the local review page before human review begins.

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

```json
{
  "caseCount": 3,
  "clipCount": 66,
  "draftPrefill": {
    "appliedClipCount": 66,
    "humanReviewRequired": true,
    "schemaVersion": "team-highlight-label-review-draft-prefill-v1",
    "skippedClipCount": 0,
    "source": "draft_bundle"
  }
}
```

Generated page evidence:

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

The review page now proves the GPT draft prefill count at generation time. The launch blocker still requires human review of the 66 clips and a real `--team-accuracy-report`; this change makes the pre-review setup easier to verify and less ambiguous.
