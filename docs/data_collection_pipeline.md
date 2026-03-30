# Data Collection Pipeline

This phase keeps the live control plane unchanged and builds offline data artifacts around the already-working runtime hierarchy.

Artifacts:

- `services/inference/datasets/gold_set.json`
- `services/inference/datasets/silver_set.json`
- `services/inference/datasets/annotation_schema.json`
- `services/inference/datasets/gold_annotations.jsonl`
- `services/inference/datasets/silver_teacher_annotations.jsonl`
- `services/inference/datasets/disagreement_queue.jsonl`

Generate the datasets:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
python3 services/inference/scripts/build_probe_datasets.py --output-dir services/inference/datasets
```

Build runtime-training splits and feature matrices:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
python3 services/inference/scripts/build_runtime_training_data.py \
  --output-dir services/inference/datasets/runtime_training
```

Train the runtime fusion labeler:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
python3 services/inference/scripts/train_runtime_model.py \
  --dataset-dir services/inference/datasets/runtime_training \
  --output services/inference/models/runtime_fusion_v1.json \
  --report-output services/inference/evals/runtime_fusion_v1_report.md
```

Run the offline probe:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
python3 services/inference/scripts/run_offline_probe.py \
  --gold-dataset services/inference/datasets/gold_annotations.jsonl \
  --silver-dataset services/inference/datasets/silver_teacher_annotations.jsonl \
  --output-dir /tmp/hoopsclips-offline-probe
```

Interpretation:

- `gold_set.json` and `silver_set.json` are the curated seed corpora used to bootstrap the generated JSONL datasets.
- `annotation_schema.json` is the canonical row schema. The older duplicate schema filenames were removed during migration.
- `runtime_training/` contains the split manifest and feature matrices for the runtime fusion model.
- `models/runtime_fusion_v1.json` is the lightweight late-fusion runtime bundle consumed by the live inference service in `shadow` or `primary` mode.
- `gold_annotations.jsonl` is the human-verified set.
- `silver_teacher_annotations.jsonl` is the teacher-only pseudo-label set.
- `disagreement_queue.jsonl` ranks clips for manual review, especially miss-vs-made, runtime-vs-teacher disagreements, and highlight-only collapses.
- The probe report summarizes separability for `eventFamily`, `outcome`, and `shotSubtype` using structured signals plus runtime and teacher outputs.
