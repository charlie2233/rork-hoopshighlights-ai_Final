from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "VIDEO_LORA_FEATURE_SCHEMA_VERSION",
    "VIDEO_LORA_SCHEMA_VERSION",
    "BasketballClipExample",
    "BasketballLabelSpaces",
    "HierarchicalVideoMAELabeler",
    "LoadedLoraRuntimeBundle",
    "LoraRunArtifact",
    "LoraRunResult",
    "apply_rslora_to_backbone",
    "build_basketball_label_spaces",
    "build_videomae_lora_examples",
    "build_videomae_lora_manifest",
    "create_videomae_backbone",
    "export_lora_logits_artifacts",
    "fit_temperature",
    "load_runtime_bundle",
    "normalize_label",
    "predict_source_path",
    "predict_with_model",
    "save_runtime_artifacts",
    "train_hierarchical_labeler",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module(".videomae_lora", __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
