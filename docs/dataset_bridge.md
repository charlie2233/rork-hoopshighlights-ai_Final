# External Basketball Dataset Bridge

This bridge converts two external annotation styles into the canonical HoopsClips hierarchical schema:

- `BARD`-style event labels
- `E-BARD`-style detection annotations

The adapter writes the same canonical row shape used by gold, silver, and disagreement-queue datasets. Teacher-style imported rows remain separate from human gold labels by default.

## Canonical row shape

Each imported row carries:

- `clipId`
- `sourceDomain`
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

## Source domains

The bridge defaults to:

- `bard:events` for BARD-style event supervision
- `ebard:detections` for E-BARD-style detection supervision

You can override the source domain on import, but keep teacher-style imports separate from human gold review rows.

## Import commands

```bash
python3 services/inference/scripts/import_external_basketball_dataset.py \
  --input /path/to/bard_events.jsonl \
  --output /path/to/canonical_rows.json \
  --source-kind bard-event

python3 services/inference/scripts/import_external_basketball_dataset.py \
  --input /path/to/ebard_detections.jsonl \
  --output /path/to/canonical_rows.json \
  --source-kind ebard-detection
```

## Evidence handling

Imported teacher-style rows keep evidence and provenance in `rawTeacherOutputs`. For example:

- original source labels
- detection lists
- bounding boxes and timestamps when available
- source dataset and source domain tags

This keeps external supervision separate from human gold while still preserving the provenance needed for audit and downstream fusion.
