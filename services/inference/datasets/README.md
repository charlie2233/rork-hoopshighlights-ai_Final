# Clip Annotation Datasets

This directory contains the offline annotation assets used by the structured-basketball probe and runtime-training pipeline.

Files:

- `gold_set.json`: curated gold seed rows used to bootstrap the human-verified dataset.
- `silver_set.json`: teacher pseudo-label seed rows kept separate from the gold set.
- `annotation_schema.json`: canonical unified clip annotation schema shared by gold and silver sets.
- `event_localization.py`: helper functions for coarse event-time spans and localization field normalization.
- `gold_annotations.jsonl`: human-verified annotations used for probe evaluation.
- `silver_teacher_annotations.jsonl`: teacher pseudo-labels kept separate from the human gold set.
- `disagreement_queue.jsonl`: clips prioritized for manual review, including event-level localization gaps and uncertainty sampling hints.
- `hard_negative_queue.jsonl`: live or shadow clips prioritized for retraining when `Highlight` or `eventFamily=other` dominates, with event-localization state preserved for active-learning triage.
- `dataset_bridge.py`: import adapters for BARD event labels, E-BARD detections, SportsMOT tracking, and TrackID3x3 fixed-camera tracking.
- `phase4_pseudo_labels/`: offline pseudo-label bundle for the in-domain slice, split into `gold_anchor_records.jsonl`, `pseudo_label_records.jsonl`, `filtered_records.jsonl`, and `manifest.json`.

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
- Phase4 adds optional event-localization fields: `eventStart`, `eventCenter`, `eventEnd`, `shotReleaseTime`, `ballNearRimTime`, `ballThroughHoopTime`, `possessionChangeTime`, and `transitionStartTime`.
- Legacy rows without localization fields still load because the Python loader injects `null` defaults before validation and export.
- Supported import adapters currently include `bard-event`, `ebard-detection`, `sportsmot-tracking`, and `trackid3x3-tracking`.
- `sportsmot:tracking` is the canonical source domain for broadcast/telemetry tracking supervision.
- `trackid3x3:fixed-camera` is the canonical source domain for fixed-camera or amateur-like tracking supervision.
- `broadcast`, `fixed_camera_indoor`, `fixed_camera_outdoor`, and `phone_casual` are now first-class source domains in the seed gold/silver corpora alongside the existing benchmark and hard-negative domains.
- Human gold rows keep teacher suggestions out of the label fields; teacher pseudo-labels stay in `silver_teacher_annotations.jsonl` and in `rawTeacherOutputs` for audit, never as a replacement for `humanVerified=true`.
- Regenerate dataset artifacts with `python3 services/inference/scripts/build_probe_datasets.py --output-dir services/inference/datasets` after editing the seed corpora.
- Regenerate runtime-training artifacts with `python3 services/inference/scripts/build_runtime_training_data.py --output-dir services/inference/datasets/runtime_training` after editing the seed corpora.
- Build a live hard-negative mining queue with `python3 services/inference/scripts/build_hard_negative_queue.py --input /tmp/batch.json --output-dir /tmp/hard-negative-queue`.

Field intent:

- `humanVerified=true` means the row is part of the human gold set.
- `humanVerified=false` means the row is teacher-labeled or otherwise pseudo-labeled.
- `rawRuntimeOutputs` stores the runtime model outputs, including VideoMAE and X-CLIP top-k signals.
- `rawTeacherOutputs` stores teacher suggestions, evidence, and confidence separately from the final label fields.
- `phase4_pseudo_labels/` keeps gold anchors separate from retained pseudo-labels and only writes confidence-gated teacher-backed rows to the pseudo-label training file.
- The phase4 pseudo-label builder is offline-only; it consumes stored annotations and does not make production teacher calls.
- `hard_negative_queue.jsonl` rows carry `priorityScore`, `sampleWeight`, `trainingWeight`, and reason tags so retraining jobs can oversample hard clips without re-scoring them.
- Both queue artifacts now also preserve `eventStartSeconds`, `eventCenterSeconds`, `eventEndSeconds`, and the other event-localization timestamps when present.
- `reviewerNotes` should capture why the row exists in the gold or silver set.
- `schemaVersion` should be treated as a migration marker, not a label signal.
- LoRA records with `trainingEligible=false` stay in the export for audit accounting, but should not be used for encoder fine-tuning until the exclusion reason is cleared, most commonly by attaching a `sourceRef`.

These files are intended to support offline probe training, disagreement mining, and dataset curation.
