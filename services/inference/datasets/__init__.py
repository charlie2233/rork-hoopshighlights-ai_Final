from __future__ import annotations

from importlib import import_module
from typing import Any

from .annotations import (
    ANNOTATION_SCHEMA_MIGRATION_NOTES_PATH,
    ANNOTATION_SCHEMA_PATH,
    ANNOTATION_SCHEMA_VERSION,
    annotation_template,
    load_annotation_rows,
    write_annotation_rows,
)

_RUNTIME_EXPORTS = {
    "LORA_DATASET_VERSION",
    "RUNTIME_TRAINING_FEATURE_VERSION",
    "build_runtime_training_bundle",
    "example_weight",
    "is_ignored",
    "lora_example_weight",
    "run_offline_probe",
}

__all__ = [
    "ANNOTATION_SCHEMA_MIGRATION_NOTES_PATH",
    "ANNOTATION_SCHEMA_PATH",
    "ANNOTATION_SCHEMA_VERSION",
    "LORA_DATASET_VERSION",
    "RUNTIME_TRAINING_FEATURE_VERSION",
    "annotation_template",
    "build_runtime_training_bundle",
    "example_weight",
    "is_ignored",
    "load_annotation_rows",
    "lora_example_weight",
    "run_offline_probe",
    "write_annotation_rows",
]


def __getattr__(name: str) -> Any:
    if name in _RUNTIME_EXPORTS:
        module = import_module(".runtime_training", __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
