# Phase 4h Acceptor Retrain Report

## Decision

- Status: `blocked_by_missing_curated_hard_negatives`.
- Reason: The standing dataset has labeled positives and unknown demo clips, but too few confirmed hard negatives for a safe acceptor weight update.
- No new detector family, SpaceJam input, family rescue threshold, or outcome mapping change is included in this branch.

## Available Supervision

- Dataset rows: `81`.
- Acceptance labels: `{"accept": 42, "unknown": 39}`.
- Hard-negative distribution: `{}`.
- Missing hard-negative buckets: `["dead_ball", "replay_or_reaction", "setup", "true_negative_non_event"]`.

## Retrain Config

- Proposal rejector loss: `focal_class_balanced` with gamma `1.75` and alpha `0.5`.
- Proposal acceptor loss: `focal_class_balanced` with gamma `2.0` and alpha `0.65`.
- Temperature scaling enabled: `True`.
- Energy-score reporting enabled: `True`.
- Outlier exposure buckets: `["dead_ball", "replay_or_reaction", "setup", "true_negative_non_event"]`.

## Training Command

```bash
uv run --with-requirements services/inference/requirements.txt \
  python3 services/inference/scripts/train_temporal_event_detector_candidates.py \
  --output-dir services/inference/evals/phase4h_acceptor_coverage_lift/retrain_candidate \
  --proposal-rejector-loss-mode focal_class_balanced \
  --proposal-rejector-focal-gamma 1.75 \
  --proposal-rejector-class-balance-alpha 0.5 \
  --proposal-acceptor-loss-mode focal_class_balanced \
  --proposal-acceptor-focal-gamma 2.0 \
  --proposal-acceptor-class-balance-alpha 0.65
```

## Recommendation

- Rerun a small smoke only after the acceptor threshold/config change is applied behind the existing shadow path.
- Hold medium-batch approval until at least the high-scoring unknown demo clips are audited and the required hard-negative buckets are represented.
