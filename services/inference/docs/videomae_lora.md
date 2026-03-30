# VideoMAE LoRA / rsLoRA Training Path

This repo now includes a lightweight PEFT training path for the VideoMAE backbone.

## What it does

- Trains a frozen-encoder baseline and an rsLoRA-adapted VideoMAE model side by side.
- Uses `target_modules="all-linear"` and `use_rslora=True` for the adapted path.
- Keeps X-CLIP frozen.
- Exports per-clip adapted logits for downstream fusion.
- Uses the gold set as the calibration/evaluation anchor and retains silver/disagreement rows in the manifest.

## Scripts

```bash
python3 services/inference/scripts/build_runtime_training_data.py --output-dir services/inference/datasets/runtime_training
python3 services/inference/scripts/train_videomae_lora.py --tiny-smoke --output-dir services/inference/models/videomae_lora_v1
```

The runtime-training export now also writes `services/inference/datasets/runtime_training/videomae_lora_v1/`, which contains the LoRA-ready candidate-window manifest and split records.

For a larger run, pass a pretrained VideoMAE checkpoint:

```bash
python3 services/inference/scripts/train_videomae_lora.py \
  --model-name MCG-NJU/videomae-base-finetuned-kinetics \
  --epochs 3 \
  --frame-count 8 \
  --output-dir services/inference/models/videomae_lora_v1
```

## Outputs

- `manifest.json` - dataset summary and split counts written by `build_runtime_training_data.py`.
- `label_spaces.json` - event family, outcome, and shot subtype vocabularies used by the training script.
- `baseline_metrics.json` - frozen baseline evaluation.
- `rslora_metrics.json` - rsLoRA evaluation and adapter metadata.
- `baseline_logits.jsonl` / `rslora_logits.jsonl` - adapted logits for downstream fusion.
- `comparison_report.md` - side-by-side summary.
- `runtime_bundle.json` - runtime bundle consumed by staging shadow/primary rollout.
- `rslora_heads.pt` - hierarchical classification heads paired with the adapter.
- `rslora_adapter/` - saved PEFT adapter weights.

## Notes

- Disagreement rows are preserved for audit and downstream fusion, but they are excluded from video training if no source video is available.
- The training path is intentionally isolated from the live control-plane contract.
- Candidate-window inference is preserved in live runtime: the LoRA bundle classifies the same candidate window that the baseline VideoMAE path sees, not the whole source video.
