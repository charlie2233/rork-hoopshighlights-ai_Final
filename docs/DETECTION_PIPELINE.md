# Detection Pipeline

HoopClips detection v2 moves from whole-video classification toward staged clip-candidate detection.

## Stages

1. Proposal: create temporal windows from native audio/visual signals or external providers.
2. Embedding/rerank: score proposals with a CLIP-like semantic adapter against product label prompts.
3. Classifier: classify each proposal with the baseline video classifier adapter.
4. Merge: combine overlapping windows and keep the strongest candidate metadata.
5. Taxonomy: map raw/research labels to product language.

## Output

The backend returns `results.clips` for old clients and `results.candidateClips` for new clients. Both carry the same clip shape. New fields include:

- `canonicalLabel`, `eventFamily`, `eventSubtype`, `shotSubtype`, `outcome`
- `rankScore`
- `topLabels` and `rawTopLabels`
- `scores.proposalScore`, `scores.embeddingScore`, `scores.classifierScore`, `scores.finalScore`
- `provenance.proposal`, `provenance.embeddingRerank`, `provenance.classifier`, `provenance.merge`, `provenance.taxonomy`

## Cloud Boundary

This stays backend-owned. iOS remains the control surface for upload, status, review, preview, download, and sharing. Do not move detection, model inference, or render production into AVFoundation.
