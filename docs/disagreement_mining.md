# Disagreement Mining

This workflow builds a review queue from unified clip annotations without changing the live inference contract.

## Annotation Contract

The queue builder consumes records that follow [`services/inference/datasets/clip_annotation_schema.json`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/datasets/clip_annotation_schema.json).

The important separation is:

- `humanVerified` and `reviewerNotes` belong to the gold path.
- `rawTeacherOutputs` belong to the teacher / silver path.
- `rawRuntimeOutputs` belong to the live runtime path.

Teacher output must never overwrite human gold labels.

## Queue Priorities

The offline queue prioritizes clips when one or more of the following are true:

- runtime and teacher disagree
- the app-facing label is only `Highlight`
- a miss-vs-made disagreement appears
- shot subtype is null even though ball / hoop evidence is strong
- teacher confidence is high while runtime confidence is low

The queue is sorted by descending priority score and then by `clipId` for deterministic output.

## Usage

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
python -m services.inference.scripts.build_disagreement_queue \
  --annotations services/inference/tests/fixtures/disagreement_annotations.json \
  --output-dir /tmp/hoops-disagreement-queue
```

The command writes:

- `disagreement_queue.json`
- `disagreement_queue.md`

## What To Review First

Prioritize the top queue entries that show:

- `Highlight` only on the runtime side
- `miss` versus `made` conflicts
- null subtype with visible ball / hoop evidence
- high-confidence teacher suggestions with low runtime confidence

Use the queue as an input to manual labeling and gold-set promotion, not as a replacement for gold labels.
