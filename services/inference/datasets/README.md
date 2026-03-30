# Dataset Seeds

This directory holds the seed manifests for the basketball labeling pipeline.

## Roles

- `clip_annotation_schema.json`: unified annotation schema for gold and silver clip records.
- `gold_set.json`: human-verified seed labels intended as the gold set.
- `silver_set.json`: teacher-labeled or unverified clips kept separate from the gold set.

## Conventions

- `humanVerified: true` means the record belongs in the gold set.
- `humanVerified: false` means the record is still silver/teacher-only and should not be treated as training truth.
- `rawRuntimeOutputs` stores runtime model outputs.
- `rawTeacherOutputs` stores offline teacher outputs and must not be merged into the gold label fields.
- `reviewerNotes` should capture why a clip belongs in the set and what the next review action is.

## Current Seed Sources

- Live staging smoke clips already validated in the structured-signal branch.
- Structured regression eval clips from `services/inference/evals/structured_basketball_eval_set.json`.
- Hard negatives that exercise abstain behavior:
  - dead-ball
  - inbound
  - dribble-only
  - replay
  - celebration
  - camera pan
  - half-court setup without an event

The goal of these files is to seed the next branch with an annotation contract, a gold/silver split, and a review queue. They are not a full annotation-tool workflow.
