# Clip Annotation Datasets

This directory contains the offline annotation assets used by the structured-basketball probe and runtime-training pipeline.

Files:

- `gold_set.json`: curated gold seed rows used to bootstrap the human-verified dataset.
- `silver_set.json`: teacher pseudo-label seed rows kept separate from the gold set.
- `annotation_schema.json`: canonical unified clip annotation schema shared by gold and silver sets.
- `gold_annotations.jsonl`: human-verified annotations used for probe evaluation.
- `silver_teacher_annotations.jsonl`: teacher pseudo-labels kept separate from the human gold set.
- `disagreement_queue.jsonl`: clips that should be prioritized for manual review.
- `hard_negative_queue.jsonl`: live or shadow clips prioritized for retraining when `Highlight` or `eventFamily=other` dominates.
- `dataset_bridge.py`: import adapters for BARD event labels, E-BARD detections, SportsMOT tracking, and TrackID3x3 fixed-camera tracking.

Runtime-training outputs:

- `runtime_training/manifest.json`: split policy, weights, and source inventory.
- `runtime_training/all_records.jsonl`: unified training records with source kind, split, weights, and derived display labels.
- `runtime_training/{train,val,test}/records.jsonl`: split-specific record dumps.
- `runtime_training/{train,val,test}/features.json`: JSON feature matrix exports for the runtime fusion model.
- `runtime_training/videomae_lora_v1/manifest.json`: LoRA-oriented split policy, sample weights, eligibility flags, and calibration-anchor counts.
- `runtime_training/videomae_lora_v1/all_records.jsonl`: candidate-window records for VideoMAE LoRA with source refs, hierarchy labels, and training eligibility.
- `runtime_training/videomae_lora_v1/{train,val,test}/records.jsonl`: split-specific LoRA records. Gold remains the main val/test calibration anchor, with a small train-support slice.

Migration notes:

- `schemaVersion` is stored on generated annotation rows and defaults to `2026-03-30` when missing on legacy seed rows.
- `annotation_schema.json` is the single source of truth; the older schema filenames are deprecated compatibility leftovers.
- Supported import adapters currently include `bard-event`, `ebard-detection`, `sportsmot-tracking`, and `trackid3x3-tracking`.
- `sportsmot:tracking` is the canonical source domain for broadcast/telemetry tracking supervision.
- `trackid3x3:fixed-camera` is the canonical source domain for fixed-camera or amateur-like tracking supervision.
- Regenerate dataset artifacts with `python3 services/inference/scripts/build_probe_datasets.py --output-dir services/inference/datasets` after editing the seed corpora.
- Regenerate runtime-training artifacts with `python3 services/inference/scripts/build_runtime_training_data.py --output-dir services/inference/datasets/runtime_training` after editing the seed corpora.
- Build a live hard-negative mining queue with `python3 services/inference/scripts/build_hard_negative_queue.py --input /tmp/batch.json --output-dir /tmp/hard-negative-queue`.

Field intent:

- `humanVerified=true` means the row is part of the human gold set.
- `humanVerified=false` means the row is teacher-labeled or otherwise pseudo-labeled.
- `rawRuntimeOutputs` stores the runtime model outputs, including VideoMAE and X-CLIP top-k signals.
- `rawTeacherOutputs` stores teacher suggestions, evidence, and confidence separately from the final label fields.
- `hard_negative_queue.jsonl` rows carry `priorityScore`, `sampleWeight`, `trainingWeight`, and reason tags so retraining jobs can oversample hard clips without re-scoring them.
- `reviewerNotes` should capture why the row exists in the gold or silver set.
- `schemaVersion` should be treated as a migration marker, not a label signal.
- LoRA records with `trainingEligible=false` stay in the export for audit accounting, but should not be used for encoder fine-tuning until the exclusion reason is cleared, most commonly by attaching a `sourceRef`.

These files are intended to support offline probe training, disagreement mining, and dataset curation.
