# Phase 3C1 Dataset Schema

This phase uses one shared clip annotation schema for both gold and silver basketball datasets.

The canonical schema is defined in [`services/inference/datasets/annotation_schema.json`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/datasets/annotation_schema.json) and includes:

- `clipId`
- `sourceDomain`
- `sourceRef`
- `schemaVersion`
- `eventFamily`
- `outcome`
- `shotSubtype`
- `ballVisible`
- `hoopVisible`
- `ballNearRim`
- `ballThroughHoopLikelihood`
- `possessionChangeLikelihood`
- `transitionLikelihood`
- `teacherConfidence`
- `humanVerified`
- `reviewerNotes`
- `rawRuntimeOutputs`
- `rawTeacherOutputs`

Migration notes:

- `schemaVersion` was added to the annotation row contract so gold/silver artifacts can be migrated and traced across phases.
- The duplicate schema files `clip_annotation_schema.json` and `clip_annotation.schema.json` are retired; `annotation_schema.json` is the only source of truth.
- `sourceRef`, `teacherConfidence`, and the numeric basketball-signal fields can be null when a clip has not been fully reconciled yet; the canonical JSON schema now matches the Python loader on those optional fields.

## Gold

Gold rows are human-verified and should be treated as the source of truth for evaluation and training. They are the clips that a reviewer has confirmed and annotated deliberately.

## Silver

Silver rows are teacher- or runtime-assisted clips that still need review. They are useful for:

- disagreement mining
- weak supervision
- reviewer prioritization
- offline probing

## Separation rule

Keep teacher outputs and runtime outputs separate from final gold labels. The `rawRuntimeOutputs` and `rawTeacherOutputs` fields preserve both views so the team can compare them without losing provenance.
