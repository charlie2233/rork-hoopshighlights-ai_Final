# Phase Launch label review execution handoff - 2026-06-03

## Purpose

Use this handoff to finish the human-reviewed launch accuracy labels for HoopClips. The local reviewer bundle exists on this workstation, but it is not launch evidence until every clip has been watched and marked reviewed by a human.

## Current proof state

- source video: `/Users/hanfei/Downloads/326_1770329282.mp4`
- review page: `/Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html`
- label status: `incomplete`
- launch evidence eligible: `false`
- complete clips: `0/54`
- incomplete clips: `54/54`
- close-review priority clips: `47`
- standard-review clips: `7`

## Browser reviewer task

Open the review page in a browser and complete all 54 clips.

Rules:

- Watch the video before marking a clip reviewed.
- Use `Next close review` first, then finish the remaining incomplete clips.
- GPT draft or prefilled fields are data-entry help only; they do not count as evidence until the video is watched and the clip is marked reviewed.
- Every final clip must have `needsLabel=false`, `reviewedByHuman=true`, `expected.teamId`, `expected.isHighlight`, `expected.eventType`, and `expected.outcome`.
- Do not paste secrets, R2 credentials, presigned URLs, API keys, private keys, account tokens, or private video contents into chat.
- Do not return full label JSON in chat unless explicitly requested; return the saved file path and summary counts instead.

Useful shortcuts from the review page:

- `S`: jump to clip start
- `E`: jump to event time
- `F`: jump to finish
- `J` / `L`: scrub backward/forward 0.5s
- `K`: play/pause
- `P`: copy HoopClips/GPT draft fields as data-entry help
- `1`: selected-team highlight
- `2`: not a highlight
- `3`: bad window
- `R`: mark reviewed and advance

## Expected reviewer output

After all 54 clips are reviewed, click `Download launch-ready labels` in the review page. The expected downloaded file is usually:

```text
~/Downloads/team_highlight_manual_labels_bundle.json
```

If review pauses before all clips are complete, click `Download progress checkpoint` and report only:

- checkpoint file path
- completed clip count
- remaining clip count
- whether any clips need a second human pass

## Apply completed labels

Only run this command after the launch-ready label bundle is downloaded. Do not use `--allow-incomplete` for launch evidence.

```bash
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --bundle ~/Downloads/team_highlight_manual_labels_bundle.json \
  --apply \
  --json
```

## Build launch accuracy report

After applying completed labels, build the launch report:

```bash
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --eval-output artifacts/team_highlight_labeling_bundle/team_highlight_eval.json \
  --report-output artifacts/team_highlight_labeling_bundle/team_highlight_accuracy_report.json \
  --json
```

Then run submission readiness with the generated report:

```bash
python3 scripts/submission_readiness_preflight.py \
  --team-accuracy-report artifacts/team_highlight_labeling_bundle/team_highlight_accuracy_report.json
```

## Completion criteria

This blocker is not closed until the final label status reports:

- `status=complete`
- `launchEvidenceEligible=true`
- `completeClipCount=54`
- `incompleteClipCount=0`

Anything short of that remains a launch blocker.
