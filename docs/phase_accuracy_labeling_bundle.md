# Phase Accuracy Labeling Bundle

## Goal

Make the missing 85% selected-team/highlight accuracy proof faster to produce without weakening the evidence gate.

This phase keeps the product architecture intact:

- Cloud owns analysis, team scan, candidate generation, GPT review, edit planning, rendering, and storage.
- Local tooling only previews source videos and fills human labels for clips that the cloud already returned.
- GPT draft labels can help, but they still require human review before launch evidence counts.

## What Changed

- `scripts/build_team_highlight_label_review_page.py` now supports multi-angle source playback.
- New options:
  - `--video-angle videoId:angleName=/absolute/path.mp4`
  - `--video-url-angle videoId:angleName=http://127.0.0.1:8787/angle.mp4`
- Clip jump buttons now seek every angle for the same `videoId` to the same timestamp.
- Added `scripts/prepare_team_highlight_labeling_bundle.py` to create:
  - `team_highlight_label_review.html`
  - `label_status.json`
  - `bundle_metadata.json`
  - `next_steps.md`

## Recommended Local Flow

Collect real cloud candidate clips:

```bash
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --duration-seconds 109.833333 \
  --case-id launch_label_case_all_001 \
  --video-id 326_1770329282 \
  --team-mode all \
  --output-dir artifacts/team_highlight_accuracy \
  --manifest artifacts/team_highlight_accuracy_manifest.json
```

Prepare the local label review bundle:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --output-dir artifacts/team_highlight_labeling_bundle \
  --json
```

For multi-angle review:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --video-angle 326_1770329282:baseline=/absolute/path/to/baseline.mp4 \
  --video-angle 326_1770329282:sideline=/absolute/path/to/sideline.mp4 \
  --output-dir artifacts/team_highlight_labeling_bundle \
  --json
```

After every clip is reviewed in the HTML page:

```bash
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --bundle ~/Downloads/team_highlight_manual_labels_bundle.json \
  --apply \
  --json

python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --eval-output artifacts/team_highlight_labeling_bundle/team_highlight_eval.json \
  --report-output artifacts/team_highlight_labeling_bundle/team_highlight_accuracy_report.json \
  --json

python3 scripts/submission_readiness_preflight.py \
  --team-accuracy-report artifacts/team_highlight_labeling_bundle/team_highlight_accuracy_report.json
```

## Labeling Coverage Needed

The launch gate still needs real labeled footage with:

- At least 2 cases and 12 scored clips.
- At least 1 all-teams case.
- Selected-team makes and misses.
- At least one selected-team block, steal, forced turnover, and defensive stop.
- At least 2 opponent highlights.
- At least 2 negative clips.
- At least 2 bad-window negatives.
- At least 1 uncertain-review clip.

Default score floors remain 85% for selected-team precision, evidence quality, recall with uncertain review, highlight precision/recall, defensive-event recall, timing quality, and outcome evidence quality.

## Public Source Shortlist

These sources are useful for building label-review coverage or taxonomy ideas. Do not treat rights-sensitive NBA/NCAA footage as product-training footage unless rights are cleared.

| Source | Use | Caveat |
| --- | --- | --- |
| Spiroudome / APIDIS family | Best multi-angle basketball seed; 8 cameras and calibration metadata. | Non-commercial research terms. |
| TrackID3x3 | 3x3 fixed-camera/drone footage with bounding boxes and pose/keypoint annotations. | Dataset CC BY 4.0, but bundled third-party code has mixed licenses. |
| TeamTrack | Full-pitch sports MOT data including basketball. | Good for team-color/tracking stress; not event/highlight labels. |
| MultiSports | Fine-grained sports action localization and basketball action vocabulary. | Competition/dataset access and non-commercial research considerations. |
| Basketball Event Detection Dataset | Closest event schema: shots, assists, blocks, rebounds, jersey colors/numbers. | Research only and NBA-footage sensitive. |
| BASKET | Large basketball skill/highlight diversity reference. | Gated dataset; use as diversity reference, not first-pass event truth. |

## Validation

```bash
python3 -m py_compile \
  scripts/build_team_highlight_label_review_page.py \
  scripts/prepare_team_highlight_labeling_bundle.py \
  scripts/test_build_team_highlight_label_review_page.py \
  scripts/test_prepare_team_highlight_labeling_bundle.py

python3 -m unittest \
  scripts.test_build_team_highlight_label_review_page \
  scripts.test_prepare_team_highlight_labeling_bundle -v
```

## Launch Notes

This phase does not by itself prove the 85% launch target. It makes the label review path easier, especially when multiple camera angles exist. The final proof still requires cloud-generated candidate clips, completed human labels, the launch accuracy report, and submission preflight with `--team-accuracy-report`.
