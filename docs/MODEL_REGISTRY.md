# Model Registry

Detection v2 introduces adapter interfaces in `ios/backend/app/model_registry.py`.

## Classifier

`VideoClassifierAdapter` exposes:

```python
def classify(window: CandidateWindow) -> ClassificationResult
```

The default classifier is `BaselineR2Plus1DAdapter`, version `r2plus1d-baseline-v1`. It wraps the existing deterministic classifier as the compatibility baseline.

`TorchvisionR2Plus1DAdapter` can load a real torchvision `r2plus1d_18` runtime behind the same interface. It is opt-in so local tests and deploys do not download model weights unexpectedly.

Environment options:

- `HOOPS_DETECTION_CLASSIFIER_ADAPTER=r2plus1d-runtime`
- `HOOPS_DETECTION_R2PLUS1D_RUNTIME=true`
- `HOOPS_DETECTION_R2PLUS1D_WEIGHTS=/path/to/state_dict.pt` for custom weights
- `HOOPS_DETECTION_R2PLUS1D_PRETRAINED=false` to disable torchvision pretrained weights
- `HOOPS_DETECTION_MODEL_DEVICE=cpu|cuda|mps`

## Embedding

`EmbeddingAdapter` exposes:

```python
def rerank(windows: Sequence[CandidateWindow], labels: Sequence[str]) -> list[EmbeddingRerankResult]
```

Built-in adapters:

- `openclip_embedding_adapter()`
- `siglip_embedding_adapter()`
- `disabled_embedding_adapter()`

The default OpenCLIP/SigLIP factories stay deterministic unless runtime mode is explicitly enabled.

Runtime adapters:

- `OpenCLIPRuntimeEmbeddingAdapter` uses `open_clip`, `torch`, and `Pillow`.
- `SigLIPRuntimeEmbeddingAdapter` uses `transformers`, `torch`, and `Pillow`.

Environment options:

- `HOOPS_DETECTION_EMBEDDING_ADAPTER=openclip-runtime`
- `HOOPS_DETECTION_EMBEDDING_ADAPTER=siglip-runtime`
- `HOOPS_DETECTION_OPENCLIP_RUNTIME=true`
- `HOOPS_DETECTION_SIGLIP_RUNTIME=true`
- `HOOPS_DETECTION_OPENCLIP_MODEL=ViT-B-32`
- `HOOPS_DETECTION_OPENCLIP_PRETRAINED=laion2b_s34b_b79k`
- `HOOPS_DETECTION_SIGLIP_MODEL=google/siglip-base-patch16-224`
- `HOOPS_DETECTION_MODEL_DEVICE=cpu|cuda|mps`

The runtime adapters lazily load optional dependencies and model weights only when selected. If runtime inputs or optional dependencies are unavailable, the adapter returns explicit fallback provenance without changing response shapes.

## Taxonomy

Product labels live in `ios/backend/app/data/basketball_taxonomy.json`. The taxonomy maps raw research labels such as `3pt`, `blocked shot`, or `audio reaction` to stable product labels and canonical metadata.
