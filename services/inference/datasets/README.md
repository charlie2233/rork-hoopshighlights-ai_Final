# Clip Annotation Datasets

This directory contains the offline annotation assets used by the structured-basketball probe.

Files:

- `annotation_schema.json`: unified clip annotation schema shared by gold and silver sets.
- `gold_annotations.jsonl`: human-verified annotations used for probe evaluation.
- `silver_teacher_annotations.jsonl`: teacher pseudo-labels kept separate from the human gold set.
- `disagreement_queue.jsonl`: clips that should be prioritized for manual review.

Field intent:

- `humanVerified=true` means the row is part of the human gold set.
- `humanVerified=false` means the row is teacher-labeled or otherwise pseudo-labeled.
- `rawRuntimeOutputs` stores the runtime model outputs, including VideoMAE and X-CLIP top-k signals.
- `rawTeacherOutputs` stores teacher suggestions, evidence, and confidence separately from the final label fields.
- `reviewerNotes` should capture why the row exists in the gold or silver set.

These files are intended to support offline probe training, disagreement mining, and dataset curation.
