# Phase Launch label bundle video source handoff - 2026-06-03

## Current status

The launch team/highlight accuracy labels are still incomplete and are not launch evidence.

Current status command:

```bash
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --label-status \
  --json
```

Current result:

- `status`: `incomplete`
- `launchEvidenceEligible`: `false`
- complete clips: `0/54`
- incomplete clips: `54/54`
- affected cases: `launch_label_case_all_001` (`0/30`) and `launch_label_case_team_001` (`0/24`)
- every clip is still missing `needsLabel=false`, `reviewedByHuman=true`, `expected.teamId`, `expected.isHighlight`, `expected.eventType`, and `expected.outcome`

## Bundle generation blocker

Attempting to generate the reviewer bundle from the committed manifest failed because the source video location is not in the repo artifact tree:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --output-dir artifacts/team_highlight_labeling_bundle \
  --title "HoopClips Launch Team Highlight Labels" \
  --json
```

The generator reported:

```text
Missing source video path or local video URL for videoId '326_1770329282'.
```

This is an intentional guard. Do not generate a fake review bundle with a placeholder video path, and do not mark the labels complete from GPT draft data. The reviewer bundle needs a real local source video path or a local browser URL for `326_1770329282`.

## Safe handoff command

Once the source video is available locally, run one of these commands from the repo root.

Local file path:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --output-dir artifacts/team_highlight_labeling_bundle \
  --video 326_1770329282=/absolute/path/to/source.mp4 \
  --title "HoopClips Launch Team Highlight Labels" \
  --json
```

Local browser URL:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --output-dir artifacts/team_highlight_labeling_bundle \
  --video-url 326_1770329282=http://127.0.0.1:8787/source.mp4 \
  --title "HoopClips Launch Team Highlight Labels" \
  --json
```

Expected bundle outputs include:

- `artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html`
- `artifacts/team_highlight_labeling_bundle/bundle_metadata.json`
- `artifacts/team_highlight_labeling_bundle/label_progress.json`
- `artifacts/team_highlight_labeling_bundle/next_steps.md`

## Launch evidence rule

The bundle is only a reviewer tool. Launch accuracy evidence remains blocked until all 54 clips have human-reviewed labels with `needsLabel=false`, `reviewedByHuman=true`, and the required expected fields filled in.
