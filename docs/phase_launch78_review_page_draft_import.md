# Phase Launch78: Review Page Draft Import

## Goal

Make the Launch71 66-clip accuracy review faster after GPT draft labels are generated, without letting GPT mark clips as reviewed or count as launch evidence.

## Change

- Added an `Import draft bundle` control to the local team-highlight review page.
- The page accepts `team-highlight-manual-label-bundle-v1` JSON bundles produced by the GPT draft helper or by the review page.
- Imported draft labels are matched by case ID and clip identity (`labelId` or `predictionClipId`).
- When the imported bundle has `humanReviewRequired=true` or a draft source, the page pre-fills expected fields but keeps the clip unchecked/unreviewed.
- The reviewer must still mark each clip reviewed before downloading a complete launch-evidence bundle.

## Guardrails

- This is a local review-page helper only.
- No iOS runtime behavior changed.
- No full videos, signed URLs, object keys, upload headers, storage credentials, or API keys are embedded in the page.
- GPT drafts remain review aids, not evidence.

## Validation

```bash
python3 -m py_compile scripts/build_team_highlight_label_review_page.py scripts/test_build_team_highlight_label_review_page.py
python3 -m unittest scripts.test_build_team_highlight_label_review_page scripts.test_draft_team_highlight_manual_labels_with_gpt -v
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
rg -n 'Import draft bundle|importDraftBundle|applyDraftBundlePayload|bundle-import|X-Amz-Signature|uploadUrl|sourceObjectKey|sourceUrl|downloadUrl|presignedUrl|resultObjectKey|uploadHeaders' \
  artifacts/team_highlight_accuracy_launch71_review.html
```

Results:

- Python compile: passed.
- Focused review/draft helper tests: 6 passed.
- Review page regenerated for 3 Launch71 cases.
- Import controls and JS were present.
- Leak scan found no signed URL, source/upload URL, object-key, result-key, or upload-header markers.
