# Phase Accuracy - Label Review Fast Fill

Date: 2026-06-01

## Goal

Move HoopClips closer to the 85% selected-team/highlight quality gate by making the local human labeling flow faster without faking launch evidence.

## Current Gate

`artifacts/team_highlight_accuracy_manifest.json` currently has 2 real cloud-analysis cases and 54 clips. The authoritative label-status command still reports:

- 0 complete clips
- 54 incomplete clips
- missing human-reviewed `expected.teamId`, `expected.isHighlight`, `expected.eventType`, `expected.outcome`, and `needsLabel=false`

That means the app is still not launch-ready on the team/highlight accuracy gate.

## Changes

- Added a `Copy prediction` button to every clip card in the local team-highlight label review page.
- Added a `p` keyboard shortcut for the active clip.
- The fast-fill action copies the existing HoopClips prediction into expected team/highlight/event/outcome fields.
- It always leaves `Reviewed` unchecked, so human review is still required before evidence counts.
- Added safe draft-bundle fallback matching by `teamMode + selectedTeamId` when case IDs changed between accuracy runs.

## Local Bundle Evidence

Regenerated the ignored local review bundle with:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --output-dir artifacts/team_highlight_labeling_bundle \
  --video 326_1770329282=/Users/hanfei/Downloads/326_1770329282.mp4 \
  --draft-bundle /Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json \
  --json
```

Result:

- review page: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html`
- GPT draft prefilled 54 clips
- fallback case matches: 2
- skipped clip from extra draft case: 1
- status remains incomplete because human review is still required

## Validation

- `python3 -m unittest scripts.test_build_team_highlight_label_review_page scripts.test_prepare_team_highlight_labeling_bundle -v` - 10 tests passed
- `python3 -m unittest discover -s scripts -p 'test_*.py'` - 139 tests passed
- `git diff --check` - passed
- generated review HTML contains `Copy prediction`, the fast-fill function, local video path, and no presigned signature text
- extracted review-page JavaScript passed `node --check`
- `python3 scripts/build_launch_team_accuracy_report.py --manifest artifacts/team_highlight_accuracy_manifest.json --label-status --json` correctly exits non-zero because labels remain incomplete

## Browser Note

Browser automation was attempted, but local Browser MCP requires a pin in this environment and the Node REPL does not have Playwright installed. The review page is still regenerated locally and can be opened directly from the path above.

## Next Step

Open the review page, use `Copy prediction` to copy the draft into fields, watch the source video, then click `Mark reviewed + next`. GPT drafts are data-entry help only and do not count as launch evidence until each clip is watched and marked reviewed. After all 54 clips are reviewed, download launch-ready labels and run the report command from `artifacts/team_highlight_labeling_bundle/next_steps.md`.
