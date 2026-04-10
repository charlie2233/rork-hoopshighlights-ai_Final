# VideoMAE LoRA vs Frozen Baseline

- Schema version: `videomae-lora-v1`
- Feature schema version: `videomae-lora-features-v1`
- Source dataset: `services/inference/datasets/runtime_training/videomae_lora_v1`
- Tiny smoke: `False`
- Event families: `['shot_attempt', 'defensive_event', 'turnover', 'transition', 'other']`
- Outcomes: `['made', 'missed', 'blocked', 'uncertain']`
- Shot subtypes: `['null', 'dunk', 'layup', 'jumper', 'three', 'putback', 'unknown']`

## Training
- Frozen baseline loss: `29.167921`
- rsLoRA loss: `26.505914`
- Baseline train examples: `3`
- rsLoRA train examples: `3`

## Metrics
- Baseline eventFamily accuracy: `1.0`
- rsLoRA eventFamily accuracy: `1.0`
- Baseline outcome accuracy: `0.0`
- rsLoRA outcome accuracy: `0.0`
- Baseline shotSubtype accuracy: `0.0`
- rsLoRA shotSubtype accuracy: `0.0`

## Artifact Preview
- Baseline first clip: `gold-shot-missed-layup-001` -> `Highlight`
- rsLoRA first clip: `gold-shot-missed-layup-001` -> `Highlight`

## Notes
- X-CLIP stays frozen; only the VideoMAE backbone receives LoRA adapters.
- Adapted logits are exported per head for downstream fusion.
- Gold clips remain the calibration anchor; disagreement rows stay in the manifest for audit.