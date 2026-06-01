# Phase Launch163 Accuracy AI Workflow

## Goal

Move focus back from branding to the product-critical path: real-footage clip accuracy proof and GPT-assisted review speed.

This phase does not change the cloud-first product boundary. Cloud analysis still creates the candidates. GPT can help draft labels from sampled keyframes, but humans still approve the labels before launch evidence counts.

## Changes

- `scripts/prepare_team_highlight_labeling_bundle.py` can now generate a GPT draft bundle directly with `--draft-with-gpt`.
- The generated review page is prefilled with GPT draft labels while keeping `humanReviewRequired=true` and every row reviewable.
- The draft path sends sampled candidate keyframes and compact metadata only. It does not send full videos, storage keys, presigned URLs, secrets, or FFmpeg commands to GPT.
- Manual label templates now preserve richer prediction context for reviewers and GPT draft labeling:
  - `eventType`
  - `motionScore`
  - `audioPeak`
  - `watchabilityScore`
  - `duplicateGroup`
  - `teamEvidence`
  - `nativeShotSignals`
  - shot/evidence quality objects when present
- GPT label drafting instructions now explicitly treat blocks, steals, forced turnovers, and defensive stops as valid highlights, even without a made shot.
- Static backend launch preflight now matches the current high-recall staging defaults:
  - GPT review candidates: 320 Free / 320 Pro
  - Analysis returned clips: 320
  - Team quick-scan candidates: 320
  - Team quick-scan total clip-frame budget: 2560
  - Team quick-scan output tokens: 18000

## One-Command Review Workspace

After collecting a real staging case:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --video-path /absolute/path/to/source.mp4 \
  --output-dir artifacts/team_highlight_labeling_bundle \
  --draft-with-gpt \
  --json
```

For multi-angle review:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --video-path /absolute/path/to/main.mp4 \
  --video-angle video_id:sideline=/absolute/path/to/sideline.mp4 \
  --video-angle video_id:baseline=/absolute/path/to/baseline.mp4 \
  --output-dir artifacts/team_highlight_labeling_bundle \
  --draft-with-gpt \
  --json
```

The output includes:

- `team_highlight_label_review.html`
- `gpt_draft_labels.json`
- `label_status.json`
- `bundle_metadata.json`
- `next_steps.md`

## Guardrails

- GPT draft labels are speed assists only.
- The review page must still download a human-reviewed `team_highlight_manual_labels_bundle.json`.
- `build_launch_team_accuracy_report.py` remains the launch evidence source.
- Do not use unlabeled GPT drafts as the 85% proof.
- Do not paste provider secrets, R2 credentials, or presigned URLs into any label files.

## Validation

```bash
python3 -m py_compile \
  scripts/make_team_highlight_label_template.py \
  scripts/draft_team_highlight_manual_labels_with_gpt.py \
  scripts/prepare_team_highlight_labeling_bundle.py \
  scripts/test_build_team_highlight_eval_payload.py \
  scripts/test_draft_team_highlight_manual_labels_with_gpt.py \
  scripts/test_prepare_team_highlight_labeling_bundle.py

python3 -m unittest \
  scripts.test_build_team_highlight_eval_payload \
  scripts.test_draft_team_highlight_manual_labels_with_gpt \
  scripts.test_prepare_team_highlight_labeling_bundle -v
```

## Launch Recommendation

Use this workflow on real iPhone-imported or staging-uploaded footage before internal TestFlight submission. The app should not be treated as launch-ready until the report passes with real labeled clips including makes, misses, blocks, steals, forced turnovers, defensive stops, bad windows, opponent clips, and uncertain review cases.
