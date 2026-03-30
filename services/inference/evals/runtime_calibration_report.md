# Runtime Calibration Report

- Schema version: `runtime-calibration-v1`
- Source dataset: `services/inference/datasets/gold_annotations.jsonl`
- Split strategy: `hash:clipId:40-40-20(train-calibration-test)`

## Holdout Metrics
### eventFamily
- Sample count: `2`
- Accuracy: `1.0`
- Mean confidence: `0.525`
- Mean calibrated confidence: `0.7916`
- ECE: `0.475`

### outcome
- Sample count: `2`
- Accuracy: `1.0`
- Mean confidence: `0.525`
- Mean calibrated confidence: `0.7619`
- ECE: `0.475`

### shotSubtype
- Sample count: `1`
- Accuracy: `1.0`
- Mean confidence: `0.63`
- Mean calibrated confidence: `0.6667`
- ECE: `0.37`

## Notes
- Calibration fits only on held-out gold rows.
- Teacher outputs remain training-only and are not read at inference time.
- Calibration tables are monotonic bin lookups applied before uncertainty gating.
