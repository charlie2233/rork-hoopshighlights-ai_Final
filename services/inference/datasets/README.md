# Clip Annotation Datasets

This directory contains the offline annotation assets used by the structured-basketball probe and runtime-training pipeline.

Files:

- `gold_set.json`: curated gold seed rows used to bootstrap the human-verified dataset.
- `silver_set.json`: teacher pseudo-label seed rows kept separate from the gold set.
- `annotation_schema.json`: canonical unified clip annotation schema shared by gold and silver sets.
- `gold_annotations.jsonl`: human-verified annotations used for probe evaluation.
- `silver_teacher_annotations.jsonl`: teacher pseudo-labels kept separate from the human gold set.
- `disagreement_queue.jsonl`: clips that should be prioritized for manual review.

Runtime-training outputs:

- `runtime_training/manifest.json`: split policy, weights, and source inventory.
- `runtime_training/all_records.jsonl`: unified training records with source kind, split, weights, and derived display labels.
- `runtime_training/{train,val,test}/records.jsonl`: split-specific record dumps.
- `runtime_training/{train,val,test}/features.json`: JSON feature matrix exports for the runtime fusion model.
- `runtime_training/videomae_lora_v1/manifest.json`: LoRA-oriented split policy, sample weights, eligibility flags, and calibration-anchor counts.
- `runtime_training/videomae_lora_v1/all_records.jsonl`: candidate-window records for VideoMAE LoRA with source refs, hierarchy labels, and training eligibility.
- `runtime_training/videomae_lora_v1/{train,val,test}/records.jsonl`: split-specific LoRA records. Gold remains the main val/test calibration anchor, with a small train-support slice.

External dataset bridge:

- `services/inference/datasets/dataset_bridge.py` maps external basketball sources into the canonical hierarchy.
- Supported source kinds:
  - `bard-event` -> `bard:events`
  - `ebard-detection` -> `ebard:detections`
  - `sportsmot-tracking` -> `sportsmot:tracking`
  - `trackid3x3-tracking` -> `trackid3x3:tracking`
- BARD-style text labels are mapped into `eventFamily`, `outcome`, and `shotSubtype` with explicit negative handling for replay, celebration, camera pan, inbound, dead-ball, setup, and other non-play clips.
- E-BARD detection rows are mapped from object detections and proximity evidence into the same hierarchical schema.
- SportsMOT and TrackID3x3 tracking rows can contribute player/ball/hoop track evidence, plus inferred transition and possession-change signals, while still preserving source-domain tags in canonical rows.
- `rawTeacherOutputs` keeps the source-specific evidence and canonical hierarchy separate from the final labels.

Migration notes:

- `schemaVersion` is stored on generated annotation rows and defaults to `2026-03-30` when missing on legacy seed rows.
- `annotation_schema.json` is the single source of truth; the older schema filenames are deprecated compatibility leftovers.
- Regenerate dataset artifacts with `python3 services/inference/scripts/build_probe_datasets.py --output-dir services/inference/datasets` after editing the seed corpora.
- Import external datasets with `python3 services/inference/scripts/import_external_basketball_dataset.py --input <input.jsonl> --output <rows.json> --source-kind <bard-event|ebard-detection|sportsmot-tracking|trackid3x3-tracking>`.
- Regenerate runtime-training artifacts with `python3 services/inference/scripts/build_runtime_training_data.py --output-dir services/inference/datasets/runtime_training` after editing the seed corpora.

Field intent:

- `humanVerified=true` means the row is part of the human gold set.
- `humanVerified=false` means the row is teacher-labeled or otherwise pseudo-labeled.
- `rawRuntimeOutputs` stores the runtime model outputs, including VideoMAE and X-CLIP top-k signals.
- `rawTeacherOutputs` stores teacher suggestions, evidence, and confidence separately from the final label fields.
- `reviewerNotes` should capture why the row exists in the gold or silver set.
- `schemaVersion` should be treated as a migration marker, not a label signal.
- LoRA records with `trainingEligible=false` stay in the export for audit accounting, but should not be used for encoder fine-tuning until the exclusion reason is cleared, most commonly by attaching a `sourceRef`.

These files are intended to support offline probe training, disagreement mining, and dataset curation.
