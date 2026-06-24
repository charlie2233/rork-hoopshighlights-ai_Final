# Model Registry

Detection v2 introduces adapter interfaces in `ios/backend/app/model_registry.py`.

## Classifier

`VideoClassifierAdapter` exposes:

```python
def classify(window: CandidateWindow) -> ClassificationResult
```

The current built-in classifier is `BaselineR2Plus1DAdapter`, version `r2plus1d-baseline-v1`. It wraps the existing deterministic classifier as the compatibility baseline. A real R2Plus1D runtime can replace the adapter without changing API response shapes.

## Embedding

`EmbeddingAdapter` exposes:

```python
def rerank(windows: Sequence[CandidateWindow], labels: Sequence[str]) -> list[EmbeddingRerankResult]
```

Built-in adapters:

- `openclip_embedding_adapter()`
- `siglip_embedding_adapter()`
- `disabled_embedding_adapter()`

The OpenCLIP/SigLIP adapters are interface-compatible lightweight adapters today. They are intentionally dependency-free in this branch so deploys and tests do not download model weights. Real model loading should stay behind the same adapter contract.

`model_registry_for_settings(settings)` chooses the adapter from:

- `semantic_rerank_enabled`
- `semantic_rerank_provider`
- `semantic_rerank_model_id`
- `semantic_rerank_batch_size`
- `semantic_rerank_cache_size`

The CLIP-like adapter batches candidate scoring, memoizes prompt/window scores with a bounded cache, and reports `latency_ms` on every `EmbeddingRerankResult`. The disabled adapter returns zero embedding scores with a `semantic_rerank_disabled` fallback reason, allowing the rest of the staged pipeline to continue.

## Taxonomy

Product labels live in `ios/backend/app/data/basketball_taxonomy.json`. The taxonomy maps raw research labels such as `3pt`, `blocked shot`, or `audio reaction` to stable product labels and canonical metadata.

The same file also owns prompt groups for semantic rerank. `BasketballTaxonomy.prompt_labels()` returns product labels, canonical labels, and grouped prompt labels so model providers can score event type, outcome, crowd reaction, team identity, bad-window, duplicate, and wrong-team concepts without hard-coding prompt strings in the pipeline.
