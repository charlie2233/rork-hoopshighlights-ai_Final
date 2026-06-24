# Detection Pipeline

HoopClips detection v2 moves from whole-video classification toward staged clip-candidate detection.

## Stages

1. Proposal: create temporal windows from native audio/visual signals or external providers.
2. Embedding/rerank: score proposals with a CLIP/SigLIP-style semantic adapter against basketball taxonomy prompts.
3. Classifier: classify each proposal with the baseline video classifier adapter.
4. Merge: combine overlapping windows and keep the strongest candidate metadata.
5. Taxonomy: map raw/research labels to product language.

Embedding rerank is selected through `model_registry_for_settings(settings)`. The feature is kill-switchable and defaults to the dependency-free OpenCLIP-compatible adapter:

- `HOOPS_SEMANTIC_RERANK_ENABLED=true|false`
- `HOOPS_SEMANTIC_RERANK_PROVIDER=openclip|siglip|disabled`
- `HOOPS_SEMANTIC_RERANK_MODEL_ID=<provider-model-id>`
- `HOOPS_SEMANTIC_RERANK_BATCH_SIZE=32`
- `HOOPS_SEMANTIC_RERANK_CACHE_SIZE=4096`

If semantic rerank is disabled or unavailable, the pipeline keeps the proposal/classifier/HoopCut/autohighlight fallback path and marks the rerank evidence with fallback metadata instead of dropping candidates.

## Output

The backend returns `results.clips` for old clients and `results.candidateClips` for new clients. Both carry the same clip shape. New fields include:

- `canonicalLabel`, `eventFamily`, `eventSubtype`, `shotSubtype`, `outcome`
- `id`, `clipId`, `rankScore`, `reviewFeedbackTags`
- `topLabels` and `rawTopLabels`
- `scores.proposalScore`, `scores.embeddingScore`, `scores.classifierScore`, `scores.finalScore`
- `provenance.proposal`, `provenance.embeddingRerank`, `provenance.classifier`, `provenance.merge`, `provenance.taxonomy`
- `rerankEvidence.provider`, `modelId`, `adapterVersion`, `promptVersion`, `killSwitch`, `embeddingScore`, `textMatches`, `errorBuckets`, `sourceIdentity`, `latencyMs`, and `fallbackReason`

`CloudAnalysisResult` also echoes job/source identity when known: `analysisJobId`, `assetId`, `assetStorageKey`, `storageKey`, and `sourceObjectKey`. These fields let the iOS review surface and edit planner correlate reranked candidates without forking the legacy response contract.

## Taxonomy Prompts

`ios/backend/app/data/basketball_taxonomy.json` contains product label mappings plus prompt groups for:

- event type
- outcome
- crowd reaction
- team identity
- review quality

The semantic adapter receives the union of product labels, canonical labels, and prompt-group labels through `BasketballTaxonomy.prompt_labels()`.

## Evaluation

`scripts/benchmark_detection_pipeline.py` now evaluates clip discovery/rerank quality rather than only printing a benchmark scaffold. It accepts either a combined fixture or separate prediction and ground-truth files:

```bash
python scripts/benchmark_detection_pipeline.py --json
python scripts/benchmark_detection_pipeline.py --fixture ios/backend/tests/fixtures/detection_eval_fixture.json --k 1 3 5 --json
```

Metrics include precision, recall, F1, nDCG, MRR, Recall@K, Precision@K, temporal IoU threshold, and error buckets for duplicate, wrong-team, bad-window, wrong-label, low-quality, false-positive, and missing-clip outcomes.

## Cloud Boundary

This stays backend-owned. iOS remains the control surface for upload, status, review, preview, download, and sharing. Do not move detection, model inference, or render production into AVFoundation.
