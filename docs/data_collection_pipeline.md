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
- `gold_annotations.jsonl` is the human-verified set.
- `silver_teacher_annotations.jsonl` is the teacher-only pseudo-label set.
- `disagreement_queue.jsonl` ranks clips for manual review, especially miss-vs-made, runtime-vs-teacher disagreements, and highlight-only collapses.
- The probe report summarizes separability for `eventFamily`, `outcome`, and `shotSubtype` using structured signals plus runtime and teacher outputs.
