# Phase Launch77: GPT Manual-Label Draft Helper

## Goal

Reduce the human-review load for the launch-grade selected-team/highlight accuracy gate without weakening the evidence standard. The 66 Launch71 clips still require human approval before they can count toward the 85% gate.

## Change

- Added `scripts/draft_team_highlight_manual_labels_with_gpt.py`.
- The helper reads the existing accuracy manifest and manual-label templates.
- It extracts sampled keyframes from each existing candidate clip only.
- It sends compact case/clip metadata plus sampled keyframes to a vision-capable OpenAI Responses model with strict Structured Outputs.
- It writes a `team-highlight-manual-label-bundle-v1` bundle with draft `expected` fields.
- It always keeps `needsLabel=true` and sets `humanReviewRequired=true`, so launch report generation remains blocked until a person approves every clip in the review page.

## Guardrails

- Does not send full videos to GPT.
- Does not let GPT produce FFmpeg commands, file paths, storage keys, URLs, or secrets.
- Does not mark labels as complete.
- Does not modify manifest label files unless the operator intentionally runs the existing apply helper with `--allow-incomplete --apply`.
- Does not change iOS runtime behavior or product architecture.

## Operator Flow

```bash
python3 scripts/draft_team_highlight_manual_labels_with_gpt.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --output ~/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --json

python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --bundle ~/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --allow-incomplete \
  --apply \
  --json

python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
```

Then review every prefilled clip in the local HTML page, mark `Reviewed`, download the final bundle, apply it without `--allow-incomplete`, and build the launch accuracy report.

## Validation

```bash
python3 -m py_compile scripts/draft_team_highlight_manual_labels_with_gpt.py scripts/test_draft_team_highlight_manual_labels_with_gpt.py
python3 -m unittest scripts.test_draft_team_highlight_manual_labels_with_gpt -v
python3 scripts/draft_team_highlight_manual_labels_with_gpt.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --mock-response /tmp/hoopclips_label_draft_mock_response.json \
  --context-output /tmp/hoopclips_label_draft_context_redacted.json \
  --output /tmp/hoopclips_label_draft_bundle.json \
  --json
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --bundle /tmp/hoopclips_label_draft_bundle.json \
  --allow-incomplete \
  --json
rg -n 'X-Amz-Signature|uploadUrl|sourceObjectKey|sourceUrl|downloadUrl|presignedUrl|resultObjectKey|uploadHeaders|/Users/hanfei|file://|AuthKey|OPENAI|sk-' \
  /tmp/hoopclips_label_draft_context_redacted.json \
  /tmp/hoopclips_label_draft_bundle.json
```

Results:

- Python compile: passed.
- Focused draft-helper tests: 4 passed.
- Real Launch71 manifest + local video path with mock structured response: produced a 3-case, 66-clip draft bundle.
- Existing apply helper accepted the draft bundle only with `--allow-incomplete`, and all 66 rows remained incomplete because `needsLabel=false` is still missing.
- Leak scan found no signed URLs, object keys, local file paths, API-key markers, or full presigned URLs in the redacted GPT context or draft bundle.
