# Accuracy Gate Status Summary

Date: 2026-07-18

## Goal

Make the remaining 85% team/highlight accuracy gate easier to inspect without weakening the launch standard or turning draft labels into evidence.

## What Changed

- Added `scripts/summarize_team_highlight_accuracy_gate.py`.
- The tool scans local ignored/generated `artifacts/team_highlight_labeling_bundle*/label_status.json` and `team_highlight_accuracy_report.json` files.
- It reports:
  - whether any label bundle is launch-evidence eligible
  - whether any accuracy report passes
  - the best review bundle by completed clips
  - the best report by pass/failure count
  - concrete next actions

## Current Local Finding

The local main-checkout artifacts still do not close the gate:

- Default launch bundle: `0/54` clips complete.
- Reduced current launch bundle: `0/18` clips complete.
- Existing older Troy bundle: `43/43` clips complete.
- Existing Troy report: real-cloud/manual-label source, but fails 12 launch thresholds, including `highlightPrecision 0.116`, `shotOutcomeEvidenceQuality 0.000`, and only one distinct video.

This keeps the preflight honest: build `50` can be ready in internal TestFlight while App Store submission remains blocked by the human-reviewed accuracy report.

## Command

```bash
python3 scripts/summarize_team_highlight_accuracy_gate.py \
  --artifacts-dir /Users/hanfei/rork-hoopshighlights-ai_Final/artifacts \
  --json
```

## Validation

```bash
python3 -m unittest scripts.test_summarize_team_highlight_accuracy_gate scripts.test_accuracy_cli_entrypoints
git diff --check
```
