# Launch Accuracy Reviewer Handoff - updated 2026-06-06

This handoff is for the human reviewer who can close the HoopClips
team-highlight accuracy evidence gate. It does not mark the gate complete and
it does not replace human review.

## Current status

The launch accuracy gate is still open, but the active review workload has been
reduced from the older noisy bundle to the current combined reduced bundle.

Current reduced review bundle:

- Bundle status: `incomplete`
- Cases: `2`
- Clips: `18`
- Complete clips: `0/18`
- Incomplete clips: `18/18`
- Review priority: `18` close-review clips
- Launch evidence eligible: `false`

Current required fields missing across the incomplete clips:

- `needsLabel=false`
- `reviewedByHuman=true`
- `expected.teamId`
- `expected.isHighlight`
- `expected.eventType`
- `expected.outcome`

GPT draft labels may speed up data entry, but they are not launch evidence.
Only set `reviewedByHuman=true` after watching the clip and confirming the
label.

## Review inputs

- Review page:
  `artifacts/team_highlight_labeling_bundle_launch_current_reduced/team_highlight_label_review.html`
- Label status:
  `artifacts/team_highlight_labeling_bundle_launch_current_reduced/label_status.json`
- Combined manifest:
  `artifacts/team_highlight_labeling_bundle_launch_current_reduced/manifest.json`
- Reduced Troy source case:
  `launch_label_troy_white_slice_10m_15m_current_reduced_001`
- Second source case:
  `launch_label_second_game_326_all_001`

The generated bundle files live under `artifacts/` and are ignored by git. They
are local reviewer tools on this workstation, not launch evidence by
themselves.

## Human review workflow

Open the current reduced review page from the repo root:

```bash
open artifacts/team_highlight_labeling_bundle_launch_current_reduced/team_highlight_label_review.html
```

Use the page to review every clip. Start with the close-review queue so
uncertain clips are handled first.

Useful review actions:

- `1`: selected-team highlight
- `2`: not a highlight
- `3`: bad window
- `S`: selected team
- `E`: event type
- `F`: outcome
- `J`, `L`, `K`: review navigation controls
- `P`: copy GPT draft fields only after watching the clip

For every final clip, confirm:

- `needsLabel=false`
- `reviewedByHuman=true`
- `expected.teamId`
- `expected.isHighlight`
- `expected.eventType`
- `expected.outcome`

Download progress checkpoints during review if needed. A checkpoint is not
launch-ready until all 18 clips are complete.

## Apply completed labels

After the review page downloads a completed
`team_highlight_manual_labels_bundle.json`, validate it first:

```bash
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_labeling_bundle_launch_current_reduced/manifest.json \
  --bundle ~/Downloads/team_highlight_manual_labels_bundle.json
```

If validation passes and all 18 clips are complete, apply it:

```bash
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_labeling_bundle_launch_current_reduced/manifest.json \
  --bundle ~/Downloads/team_highlight_manual_labels_bundle.json \
  --apply
```

Do not use `--allow-incomplete` for launch evidence.

## Build the launch accuracy report

After applying the completed labels, build the launch-grade report:

```bash
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_labeling_bundle_launch_current_reduced/manifest.json \
  --eval-output artifacts/team_highlight_labeling_bundle_launch_current_reduced/team_highlight_eval.json \
  --report-output artifacts/team_highlight_labeling_bundle_launch_current_reduced/team_highlight_accuracy_report.json
```

Then run submission readiness with the report and current bundle path:

```bash
python3 scripts/submission_readiness_preflight.py \
  --labeling-bundle-dir artifacts/team_highlight_labeling_bundle_launch_current_reduced \
  --team-accuracy-report artifacts/team_highlight_labeling_bundle_launch_current_reduced/team_highlight_accuracy_report.json
```

## Completion evidence to report back

Report only non-secret status:

- `label_status.json` shows `18/18` complete.
- The completed bundle was applied without `--allow-incomplete`.
- The launch accuracy report path.
- The submission readiness result and any failing check names.

Do not report source video URLs, object keys, upload URLs, tokens, secrets,
credentials, private keys, or full presigned URLs.

## Current conclusion

The accuracy gate remains open. The next launch-critical action is human review
of all 18 current reduced clips, then applying the completed bundle, building
the launch accuracy report, and rerunning submission readiness with that report.
