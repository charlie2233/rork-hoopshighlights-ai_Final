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

## Taxonomy

Product labels live in `ios/backend/app/data/basketball_taxonomy.json`. The taxonomy maps raw research labels such as `3pt`, `blocked shot`, or `audio reaction` to stable product labels and canonical metadata.
