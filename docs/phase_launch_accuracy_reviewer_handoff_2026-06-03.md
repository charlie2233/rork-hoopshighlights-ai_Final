# Launch Accuracy Reviewer Handoff - 2026-06-03

This handoff is for the human reviewer who can close the HoopClips
team-highlight accuracy evidence gate. It does not mark the gate complete and
does not replace human review.

## Current status

- Label bundle status: `incomplete`
- Cases: `2`
- Clips: `54`
- Complete clips: `0`
- Incomplete clips: `54`
- Close-review priority clips: `49`
- Standard-review clips: `5`

Current required fields missing across all 54 clips:

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
  `artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html`
- Label status:
  `artifacts/team_highlight_labeling_bundle/label_status.json`
- Manifest:
  `artifacts/team_highlight_accuracy_manifest.json`
- Source label templates:
  - `artifacts/team_highlight_accuracy/launch_label_case_all_001/manual_labels_template.json`
  - `artifacts/team_highlight_accuracy/launch_label_case_team_001/manual_labels_template.json`

The mapped draft bundle under
`artifacts/team_highlight_labeling_bundle/temp_mapped_draft/` is a review aid
only. Do not apply it as final launch evidence unless every clip has been
watched and marked human-reviewed in the review page.

## Human review workflow

Open the review page from the repo root:

```bash
open artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html
```

Use the page to review every clip. Start with the `Next close review` queue so
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
launch-ready until all 54 clips are complete.

## Apply completed labels

After the review page downloads a completed
`team_highlight_manual_labels_bundle.json`, validate it first:

```bash
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --bundle ~/Downloads/team_highlight_manual_labels_bundle.json
```

If validation passes and all 54 clips are complete, apply it:

```bash
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --bundle ~/Downloads/team_highlight_manual_labels_bundle.json \
  --apply
```

Do not use `--allow-incomplete` for launch evidence.

## Build the launch accuracy report

After applying the completed labels, build the launch-grade report:

```bash
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --eval-output artifacts/team_highlight_accuracy/team_highlight_eval_payload.json \
  --report-output artifacts/team_highlight_accuracy/team_highlight_accuracy_report.json
```

Then run submission readiness with the report:

```bash
python3 scripts/submission_readiness_preflight.py \
  --team-accuracy-report artifacts/team_highlight_accuracy/team_highlight_accuracy_report.json
```

## Completion evidence to report back

Report only non-secret status:

- `label_status.json` shows `54/54` complete.
- The completed bundle was applied without `--allow-incomplete`.
- The launch accuracy report path.
- The submission readiness result and any failing check names.

Do not report source video URLs, object keys, upload URLs, tokens, secrets,
credentials, private keys, or full presigned URLs.

## Current conclusion

The accuracy gate is still open. The next launch-critical action is human review
of all 54 clips, then applying the completed bundle, building the launch
accuracy report, and rerunning submission readiness with that report.

## 2026-06-03 current label-status check

Current command:

```bash
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --label-status \
  --json
```

Result remains incomplete and not launch evidence:

- Status: `incomplete`
- Launch evidence eligible: `false`
- Cases: `2`
- Clips: `54`
- Complete clips: `0`
- Incomplete clips: `54`
- `launch_label_case_all_001`: `0/30` complete
- `launch_label_case_team_001`: `0/24` complete

Missing fields still total `54` each for:

- `needsLabel=false`
- `reviewedByHuman=true`
- `expected.teamId`
- `expected.isHighlight`
- `expected.eventType`
- `expected.outcome`

The command exits non-zero while labels are incomplete. That is expected and
keeps this gate blocked until a human reviewer completes all 54 clips, applies
the final bundle without `--allow-incomplete`, and rebuilds the launch accuracy
report.
