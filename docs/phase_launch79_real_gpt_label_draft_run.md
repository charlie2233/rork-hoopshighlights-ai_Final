# Phase Launch79: Real GPT Label Draft Run

## Goal

Move the Launch71 selected-team/highlight accuracy gate from blank manual labels toward a reviewable draft, while preserving the requirement that a human must approve every clip before the 85% launch report can count.

## What Ran

Secret Manager access was available locally, so the OpenAI key was passed only as a process environment variable and was not printed, written to repo files, logged, or copied into documentation.

The GPT draft helper was run once per case to keep each vision request bounded. The credential came from Secret Manager and was injected only into the process environment.

```bash
for CASE_ID in launch71_downloads_326_team_black launch71_downloads_326_team_white launch71_downloads_326_all; do
  python3 scripts/draft_team_highlight_manual_labels_with_gpt.py \
    --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
    --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
    --case "$CASE_ID" \
    --frames-per-clip 3 \
    --output "/tmp/${CASE_ID}_draft_bundle.json" \
    --json
done
```

Outputs:

- `launch71_downloads_326_team_black`: 25 draft clips.
- `launch71_downloads_326_team_white`: 11 draft clips.
- `launch71_downloads_326_all`: 30 draft clips.
- Merged local bundle: `/Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json`.

## Local Application

The draft bundle was applied to the ignored local Launch71 label templates with `--allow-incomplete --apply`, then the review page was regenerated:

```bash
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --bundle /Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --allow-incomplete \
  --apply \
  --json

python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
```

Label status after application:

- 66 / 66 clips now have draft `expected.teamId`, `expected.isHighlight`, `expected.eventType`, and `expected.outcome`.
- 0 / 66 clips are complete for launch evidence.
- The only remaining missing field is `needsLabel=false` on all 66 clips, which requires human review.

## Guardrails

- Full videos were not sent to GPT; only existing candidate clip windows and sampled keyframes were used.
- The draft bundle keeps `humanReviewRequired=true`.
- The applied local labels keep `needsLabel=true`.
- The launch accuracy report still cannot be built until human review marks every clip complete.
- Generated draft artifacts remain outside tracked source or under ignored `artifacts/`.

## Leak Scan

```bash
rg -n 'X-Amz-Signature|uploadUrl|sourceObjectKey|sourceUrl|downloadUrl|presignedUrl|resultObjectKey|uploadHeaders|AuthKey|OPENAI|sk-' \
  /Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json \
  artifacts/team_highlight_accuracy_launch71_review.html \
  artifacts/team_highlight_accuracy_launch71/launch71_downloads_326_team_black/manual_labels_template.json \
  artifacts/team_highlight_accuracy_launch71/launch71_downloads_326_team_white/manual_labels_template.json \
  artifacts/team_highlight_accuracy_launch71/launch71_downloads_326_all/manual_labels_template.json
```

Result: no matches.

## Next Human Step

Open `artifacts/team_highlight_accuracy_launch71_review.html`, verify every prefilled label against the source video, mark each reviewed clip, download the final bundle, apply it without `--allow-incomplete`, then build the launch accuracy report.
