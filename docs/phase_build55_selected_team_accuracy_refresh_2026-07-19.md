# Build 55 Selected-Team Accuracy Refresh

## Scope

This pass exercised the current staging team-selection path with real basketball footage and repaired launch-evidence tooling that could misclassify refreshed analyses. It did not change upload, detection, editing, rendering, or production thresholds.

## Real Staging Result

The five-minute Troy versus El Dorado fixture completed the current staging flow:

- team scan detected black/yellow and white/red jersey groups;
- white was selected before analysis;
- cloud analysis completed and returned 11 clips;
- all 11 current predictions mapped one-to-one to completed human-reviewed time windows;
- 32 older reviewed windows had no matching current prediction.

The corrected selected-team evaluation remains failed:

- highlight precision: `0.0909`;
- highlight recall: `0.5`;
- selected-team recall with uncertain clips: `0.5`;
- selected-team highlights: `2` of the required `6`;
- opponent highlights: `3`;
- selected-team defensive events: `0` of the required `2`;
- shot-outcome evidence quality: `0.0`.

This probe reuses the same source game and the same 43 human-reviewed labels as the primary all-teams report. It is useful current selected-team evidence, but it is not counted as a second independent launch case.

A separate 109.8-second real-game black-team staging run also completed with two detected teams and eight returned clips. Its labels remain unreviewed, so it is diagnostic evidence only and does not count toward the launch accuracy gate.

## Evidence Tooling Fixes

`build_team_highlight_eval_payload.py` now:

- treats an explicit `--selected-team-id` as a real team-mode override even when a reusable label file was originally captured in all-teams mode;
- prefers detected-team options from the current cloud analysis, falling back to label-file options only when current analysis has none.

`build_launch_team_accuracy_report.py` now exposes `--remap-stale-predictions-by-time` and accepts `remapStalePredictionsByTime` per manifest case. This lets the multi-case report path use the existing one-to-one time-overlap contract after cloud prediction IDs change.

These changes affect evidence assembly only. They do not relabel clips, create human-review claims, or weaken the `0.85` thresholds.

## Reproduce

Build the selected-team payload from current local launch artifacts:

```bash
python3 scripts/build_team_highlight_eval_payload.py \
  --analysis-result artifacts/team_highlight_accuracy_troy_selected_current/launch_label_troy_white_slice_10m_15m_team_white_current_001/analysis_result.json \
  --labels artifacts/team_highlight_accuracy_troy/launch_label_troy_white_slice_10m_15m_all_001/manual_labels_template.json \
  --case-id launch_label_troy_white_slice_10m_15m_team_white_current_001 \
  --selected-team-id team_white \
  --allow-unlabeled-predictions \
  --remap-stale-predictions-by-time \
  --output /tmp/hoopclips-troy-white-current-eval.json
```

Then evaluate without threshold overrides:

```bash
python3 scripts/evaluate_team_highlight_accuracy.py \
  --json /tmp/hoopclips-troy-white-current-eval.json
```

## Verification

```text
python3 -m unittest -v scripts.test_build_team_highlight_eval_payload scripts.test_build_launch_team_accuracy_report
Ran 22 tests: PASS

python3 -m unittest -v scripts.test_build_team_highlight_eval_payload scripts.test_build_launch_team_accuracy_report scripts.test_team_highlight_accuracy_eval scripts.test_validate_app_store_submission_package
Ran 61 tests: PASS

python3 -m unittest -v scripts.test_launch_backend_config_preflight scripts.test_submission_readiness_preflight
Ran 71 tests: PASS
```

The static backend/config preflight reported `85` passes, `12` expected production warnings, and `0` failures. The App Store package validator passed structurally and continued to report the external/operator launch blockers.

## Launch Decision

Build 55 remains valid for internal TestFlight, but public App Store submission is still blocked. Accuracy work still needs another independently human-reviewed real game with selected-team makes, misses, blocks, steals, forced turnovers, defensive stops, uncertain clips, opponent highlights, and bad-window negatives. The exact production build must also pass installed-device cloud upload, analysis, Review, AI Edit, render, preview, save, and share smoke before release.
