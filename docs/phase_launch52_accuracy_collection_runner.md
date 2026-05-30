# Phase Launch52: Accuracy Collection Runner

## Goal

Make it faster to collect the real cloud-analysis and manual-label artifacts required for the launch-grade selected-team/highlight accuracy report.

## What Changed

- Added `scripts/collect_team_highlight_accuracy_case.py`.
- Added tests in `scripts/test_collect_team_highlight_accuracy_case.py`.
- Added `artifacts/` to `.gitignore` so real analysis exports and manual labels are not accidentally committed.

## Runner Behavior

The runner:

1. Uploads a real basketball clip to the staging Worker.
2. Runs cloud team scan for selected-team mode, or starts all-teams analysis directly.
3. Starts cloud analysis with the selected jersey-color team or all-teams mode.
4. Polls the Worker job until terminal state.
5. Writes:
   - `analysis_result.json`
   - `manual_labels_template.json`
   - a manifest entry compatible with `scripts/build_launch_team_accuracy_report.py`

It does not inspect video pixels locally, run local analysis, compose video, render video, call GPT directly from the client, or print presigned URLs.

## Example

```sh
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /path/to/real-basketball-clip.mp4 \
  --duration-seconds 30 \
  --case-id internal_case_001 \
  --video-id internal_video_001 \
  --team-mode team \
  --selected-color-label black
```

After labeling every row in `manual_labels_template.json`, build the launch report:

```sh
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --eval-output artifacts/team_highlight_eval.json \
  --report-output artifacts/team_highlight_accuracy_report.json \
  --json
```

The report must pass the default launch thresholds before claiming the 85% selected-team/highlight quality target.

## Launch Notes

- Use at least two real footage cases.
- Include selected-team makes, misses, blocks, steals, forced turnovers, defensive stops, opponent highlights, uncertain review clips, all-teams mode, and bad-window negatives.
- Keep clips marked uncertain in the labels; do not delete hard cases to inflate precision.
- Do not paste secrets, storage credentials, R2 object keys, or full presigned URLs into docs or chat.

## Validation

Commands:

```sh
python3 -m py_compile scripts/collect_team_highlight_accuracy_case.py
python3 -m unittest scripts.test_collect_team_highlight_accuracy_case -v
git diff --check
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Results:

- Collector compile: passed.
- Collector tests: 2 passed.
- `git diff --check`: passed.
- Full script test discovery: 111 passed.
