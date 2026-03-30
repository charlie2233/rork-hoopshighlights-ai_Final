# Phase 3C1 Dataset Schema

This phase uses one shared clip annotation schema for both gold and silver basketball datasets.

The schema is defined in [`services/inference/datasets/clip_annotation.schema.json`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/datasets/clip_annotation.schema.json) and includes:

- `clipId`
- `sourceDomain`
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
