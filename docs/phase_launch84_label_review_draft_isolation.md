# Phase Launch84: Label Review Draft Isolation

## Scope

This pass protects the launch-grade label review workflow from stale browser-local drafts. It only changes the local manual-review helper page; it does not affect iOS runtime, cloud rendering, GPT selection, or launch thresholds.

Branch under test: `codex/phase-launch70-editing-analysis-progress`.

## Issue

The review page saved local drafts under a key derived only from case IDs. After adding GPT draft prefill, an older non-prefilled local draft for the same cases could restore on page load and hide the newly prefilled GPT labels. That would slow down the human 85% accuracy gate and make the review page look blank again.

## Change

`draftStorageKey()` now includes the prefill state:

- `source`
- `appliedClipCount`
- `skippedClipCount`
- whether `humanReviewRequired` is true

Pages without a prefill still use an explicit `prefill:none` suffix. Prefilled and non-prefilled review sessions therefore no longer overwrite each other in localStorage.

## Evidence

Regenerated the Launch71 review page with the GPT draft bundle:

```bash
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --draft-bundle /Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
```

Result:

- Case count: `3`.
- Generated page still shows `GPT draft prefilled 66 clips. Human review is still required.`
- Generated page contains the prefill-aware local draft key logic.
- Generated page has 66 clip cards.
- Generated page has 0 reviewed checkboxes checked.
- Generated page scan found no `X-Amz-Signature`, `uploadUrl`, `sourceObjectKey`, `sourceUrl`, `downloadUrl`, `presignedUrl`, `resultObjectKey`, `uploadHeaders`, `AKIA`, `ASIA`, OpenAI key-looking values, `Approve all`, or `markAllReviewed`.

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

The remaining accuracy blocker still needs human review of the 66 prefilled clips and a generated `--team-accuracy-report`. This change makes that review path more reliable by preventing stale local drafts from erasing the GPT-preloaded starting point.
