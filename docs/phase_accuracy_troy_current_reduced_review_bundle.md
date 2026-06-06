# Troy current reduced review bundle

Date: 2026-06-06
Branch: `codex/phase-clip1-gpt-led-highlight-editor`
Source commit: `bf3d0c8f5436abafb2b5b15ca1f5637b91eb48a9`

## What changed

A new human-review bundle was generated from the current source-scaled trimmed Troy analysis so the reviewer does not have to work through the older noisy/redundant launch bundle first.

This bundle uses:

- Source analysis: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_accuracy_troy_current/launch_label_troy_white_slice_10m_15m_all_001/analysis_result.json`
- Source video: `/Users/hanfei/Downloads/HoopClips_Troy_vs_ElDorado_2026-01-28_troy_white_slice_10m-15m.mp4`
- Selected team: `team_white`
- Selected team color label: `white`
- Review window padding: `2.0s` pre-roll, `4.0s` post-roll
- Temporal dedupe: enabled by default

## Generated review bundle

Ignored/generated artifacts:

- Review page: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle_troy_current_reduced/team_highlight_label_review.html`
- Label status: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle_troy_current_reduced/label_status.json`
- Review queue: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle_troy_current_reduced/review_queue.md`
- Manifest: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle_troy_current_reduced/manifest.json`
- Manual-label template: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle_troy_current_reduced/manual_labels_template.json`

Bundle summary from `prepare_team_highlight_labeling_bundle.py`:

```json
{
  "caseCount": 1,
  "clipCount": 10,
  "completeClipCount": 0,
  "incompleteClipCount": 10,
  "reviewPriorityCounts": {
    "needs_close_review": 10
  },
  "status": "incomplete"
}
```

## Commands run

```bash
mkdir -p artifacts/team_highlight_labeling_bundle_troy_current_reduced

python3 scripts/make_team_highlight_label_template.py \
  --analysis-result artifacts/team_highlight_accuracy_troy_current/launch_label_troy_white_slice_10m_15m_all_001/analysis_result.json \
  --output artifacts/team_highlight_labeling_bundle_troy_current_reduced/manual_labels_template.json \
  --case-id launch_label_troy_white_slice_10m_15m_current_reduced_001 \
  --video-id troy_el_dorado_2026_01_28_slice_10m_15m_current_reduced \
  --team-mode team \
  --selected-team-id team_white \
  --selected-team-color-label white \
  --clip-window-pre-roll-seconds 2.0 \
  --clip-window-post-roll-seconds 4.0

python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_labeling_bundle_troy_current_reduced/manifest.json \
  --output-dir artifacts/team_highlight_labeling_bundle_troy_current_reduced \
  --video troy_el_dorado_2026_01_28_slice_10m_15m_current_reduced=/Users/hanfei/Downloads/HoopClips_Troy_vs_ElDorado_2026-01-28_troy_white_slice_10m-15m.mp4 \
  --title 'Troy reduced current review - 11 clips' \
  --json
```

The manifest uses absolute paths for `analysisResult` and `labels` because the review-bundle builder resolves manifest entries relative to the manifest directory.

## What this proves

This proves the current trimmed analysis can be converted into a much smaller human-review workload:

- Old launch bundle status: `0/54` reviewed.
- Older Troy retained-candidate evaluation had `43` retained candidates and poor precision.
- Current reduced Troy review bundle: `10` clips needing human review.

## What this does not prove yet

This does not close the launch accuracy gate yet.

Remaining accuracy work:

1. Human-review all 10 reduced Troy clips.
2. Save/export the completed manual labels.
3. Rebuild the launch accuracy report from completed labels.
4. Add at least one more real labeled case.
5. Confirm the final launch report reaches the required useful/accurate selected-team threshold and has no opponent leakage or miss-to-made drift.

