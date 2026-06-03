# Phase Launch label bundle handoff - 2026-06-03

## Current status

The launch team/highlight reviewer bundle can now be generated locally because the source video was found on this workstation. The bundle is still not launch evidence because the human labels remain incomplete.

Current label status:

- `status`: `incomplete`
- `launchEvidenceEligible`: `false`
- complete clips: `0/54`
- incomplete clips: `54/54`
- affected cases: `launch_label_case_all_001` (`0/30`) and `launch_label_case_team_001` (`0/24`)
- every clip is still missing `needsLabel=false`, `reviewedByHuman=true`, `expected.teamId`, `expected.isHighlight`, `expected.eventType`, and `expected.outcome`

## Source video input

The required local source video for manifest video ID `326_1770329282` is available at:

```text
/Users/hanfei/Downloads/326_1770329282.mp4
```

Do not commit the source video. It is only used as the local review media input for the label-review page.

## Bundle generation command

The reviewer bundle was generated from the repo root with:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --output-dir artifacts/team_highlight_labeling_bundle \
  --video 326_1770329282=/Users/hanfei/Downloads/326_1770329282.mp4 \
  --title "HoopClips Launch Team Highlight Labels" \
  --json
```

Generator result:

- `schemaVersion`: `team-highlight-labeling-bundle-v1`
- `status`: `incomplete`
- `caseCount`: `2`
- `clipCount`: `54`
- `completeClipCount`: `0`
- `incompleteClipCount`: `54`
- review priorities: `47` `needs_close_review`, `7` `standard_review`
- video angles: `1`

Generated local bundle outputs:

- `artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html`
- `artifacts/team_highlight_labeling_bundle/bundle_metadata.json`
- `artifacts/team_highlight_labeling_bundle/label_status.json`
- `artifacts/team_highlight_labeling_bundle/next_steps.md`
- `artifacts/team_highlight_labeling_bundle/temp_mapped_draft/launch_label_case_all_001_manual_labels_template_mapped.json`
- `artifacts/team_highlight_labeling_bundle/temp_mapped_draft/launch_label_case_team_001_manual_labels_template_mapped.json`
- `artifacts/team_highlight_labeling_bundle/temp_mapped_draft/launch_label_mapped_manifest.json`
- `artifacts/team_highlight_labeling_bundle/temp_mapped_draft/launch_label_mapped_manifest_abs.json`
- `artifacts/team_highlight_labeling_bundle/temp_mapped_draft/team_highlight_accuracy_report.json`
- `artifacts/team_highlight_labeling_bundle/temp_mapped_draft/team_highlight_eval.json`

These bundle files are ignored by `.gitignore` through the `artifacts/` rule. They are present locally for review on this workstation, but they are not committed to the branch.

## Launch evidence rule

The bundle is only a reviewer tool. Launch accuracy evidence remains blocked until all 54 clips have human-reviewed labels with `needsLabel=false`, `reviewedByHuman=true`, and the required expected fields filled in. GPT draft labels and generated bundle files do not count as human-reviewed launch evidence.
