# HoopsClips Dataset Schema

This folder defines the clip-annotation contract used by both gold and silver basketball datasets.

## Unified clip annotation

Use [`clip_annotation.schema.json`](./clip_annotation.schema.json) for every clip-level row. The schema is intentionally shared so that:

- gold annotations and silver annotations stay structurally compatible
- runtime outputs can be compared directly against teacher outputs
- human review can override teacher labels without rewriting the data shape

Required fields capture:

- clip identity and source provenance
- hierarchy labels: `eventFamily`, `outcome`, `shotSubtype`
- structured basketball evidence
- human verification state
- raw runtime and teacher payloads kept separate

## Gold vs Silver

Gold rows are human-verified. They are the source of truth for evaluation and training targets.

Silver rows are teacher- or runtime-assisted annotations that have not been fully human verified yet. They are useful for:

- disagreement mining
- bootstrapping review queues
- offline probing
- pseudo-label generation

Keep the two tiers separate by using `humanVerified` plus `reviewerNotes` and the raw payload fields:

- `rawRuntimeOutputs` for the live system output
- `rawTeacherOutputs` for the offline teacher output

Do not merge teacher labels into gold labels in place. Promote silver rows into gold only after human review.
