# Clip Annotation Datasets

This directory contains the offline annotation assets used by the structured-basketball probe.

Files:

- `gold_set.json`: curated gold seed rows used to bootstrap the human-verified dataset.
- `silver_set.json`: teacher pseudo-label seed rows kept separate from the gold set.
- `annotation_schema.json`: canonical unified clip annotation schema shared by gold and silver sets.
- `gold_annotations.jsonl`: human-verified annotations used for probe evaluation.
- `silver_teacher_annotations.jsonl`: teacher pseudo-labels kept separate from the human gold set.
- `disagreement_queue.jsonl`: clips that should be prioritized for manual review.

Migration notes:

- `schemaVersion` is now required on every annotation row and is set to `2026-03-30` for this phase.
- `clip_annotation_schema.json` and `clip_annotation.schema.json` were removed; use `annotation_schema.json` as the single source of truth.
- Regenerate dataset artifacts with `python3 services/inference/scripts/build_probe_datasets.py --output-dir services/inference/datasets` after editing the seed corpora.

Field intent:

- `humanVerified=true` means the row is part of the human gold set.
- `humanVerified=false` means the row is teacher-labeled or otherwise pseudo-labeled.
- `rawRuntimeOutputs` stores the runtime model outputs, including VideoMAE and X-CLIP top-k signals.
- `rawTeacherOutputs` stores teacher suggestions, evidence, and confidence separately from the final label fields.
- `reviewerNotes` should capture why the row exists in the gold or silver set.
- `schemaVersion` should be treated as a migration marker, not a label signal.

These files are intended to support offline probe training, disagreement mining, and dataset curation.
