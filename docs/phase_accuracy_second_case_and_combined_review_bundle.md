# Second accuracy case and combined current review bundle

Date: 2026-06-06
Branch: `codex/phase-clip1-gpt-led-highlight-editor`
Base deployed commit before this handoff: `e6cefef3b2c16d9b86e620269f4e9b88e9dbc869`

## Purpose

The launch accuracy gate needs more than one real labeled footage case and cannot rely on the older noisy/redundant bundle alone. This handoff adds a second real basketball source candidate and creates a combined reduced review bundle so human review can continue with a much smaller workload.

## Second case collected through staging cloud analysis

Source video:

- `/Users/hanfei/Downloads/326_1770329282.mp4`

Video metadata from `ffprobe`:

- Duration: `109.833333s`
- Resolution: `1280x592`
- Has audio: yes

Cloud collection command:

```bash
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --duration-seconds 109.833333 \
  --case-id launch_label_second_game_326_all_001 \
  --video-id second_game_326_109s_all \
  --team-mode all \
  --output-dir artifacts/team_highlight_accuracy_second_game_326 \
  --manifest artifacts/team_highlight_accuracy_second_game_326_manifest.json \
  --timeout-seconds 900 \
  --upload-timeout-seconds 180
```

Cloud result:

```json
{
  "status": "pass",
  "finalJobStatus": "completed",
  "jobId": "ddf56a2eb4674d86a4e2345dba8d548b",
  "teamMode": "all",
  "clipCount": 8,
  "detectedTeamCount": 0,
  "videoId": "second_game_326_109s_all",
  "workerUrl": "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"
}
```

Generated ignored artifacts:

- Analysis result: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_accuracy_second_game_326/launch_label_second_game_326_all_001/analysis_result.json`
- Manual labels template: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_accuracy_second_game_326/launch_label_second_game_326_all_001/manual_labels_template.json`
- Manifest: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_accuracy_second_game_326_manifest.json`

## Second-case review bundle

Command:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_second_game_326_manifest.json \
  --output-dir artifacts/team_highlight_labeling_bundle_second_game_326 \
  --video second_game_326_109s_all=/Users/hanfei/Downloads/326_1770329282.mp4 \
  --title 'Second game 326 review - 8 clips' \
  --json
```

Result:

```json
{
  "caseCount": 1,
  "clipCount": 8,
  "completeClipCount": 0,
  "incompleteClipCount": 8,
  "reviewPriorityCounts": {
    "needs_close_review": 8
  },
  "status": "incomplete"
}
```

Review page:

- `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle_second_game_326/team_highlight_label_review.html`

## Combined current reduced launch-review bundle

A combined review bundle was created with:

1. Reduced Troy current case: `10` clips, `team_white`, color `white`.
2. Second 326 case: `8` clips, all-teams mode.

Review page:

- `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle_launch_current_reduced/team_highlight_label_review.html`

Label status:

- `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle_launch_current_reduced/label_status.json`

Bundle summary:

```json
{
  "caseCount": 2,
  "clipCount": 18,
  "completeClipCount": 0,
  "incompleteClipCount": 18,
  "reviewPriorityCounts": {
    "needs_close_review": 18
  },
  "status": "incomplete"
}
```

## Accuracy caveats

This is real progress but does not close the launch accuracy gate yet.

Important caveats:

- The second case is all-teams mode because no reliable selected-team/color instruction was available for `/Users/hanfei/Downloads/326_1770329282.mp4`.
- The cloud run returned `detectedTeamCount: 0`, so it should not be used as selected-team proof unless a follow-up selected-team case is collected with a known team/color.
- Both cases still require human labels before evaluation.
- GPT draft labels do not satisfy the launch gate unless each clip is human-reviewed and exported with `reviewedByHuman=true` and `needsLabel=false`.

## Remaining accuracy steps

1. Open the combined review page and human-review all `18` clips.
2. Export/save the completed labels.
3. Rebuild the launch accuracy report from the completed labels.
4. If selected-team proof is still below threshold, collect another short case with a known team/color and rerun in `team` mode.
5. Confirm the final report hits the launch target and has no opponent leakage or miss-to-made drift.
