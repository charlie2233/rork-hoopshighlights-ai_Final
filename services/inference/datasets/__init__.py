from __future__ import annotations

from importlib import import_module
from typing import Any

from .annotations import (
    ANNOTATION_SCHEMA_MIGRATION_NOTES_PATH,
    ANNOTATION_SCHEMA_PATH,
    ANNOTATION_SCHEMA_VERSION,
    ClipAnnotation,
    annotation_template,
    load_annotation_rows,
    write_annotation_rows,
)
from .hard_negative_mining import build_hard_negative_report, build_hard_negative_queue, load_live_payloads

_RUNTIME_EXPORTS = {
    "LORA_DATASET_VERSION",
    "RUNTIME_TRAINING_FEATURE_VERSION",
    "build_runtime_training_bundle",
    "example_weight",
    "is_ignored",
    "lora_example_weight",
}

_TEACHER_EXPORTS = {
    "TEACHER_SUPERVISION_DATASET_VERSION",
    "build_teacher_supervision_bundle",
    "teacher_supervision_weight",
    "teacher_supervision_weight_components",
}

__all__ = [
    "ANNOTATION_SCHEMA_MIGRATION_NOTES_PATH",
    "ANNOTATION_SCHEMA_PATH",
    "ANNOTATION_SCHEMA_VERSION",
    "ClipAnnotation",
    "LORA_DATASET_VERSION",
    "RUNTIME_TRAINING_FEATURE_VERSION",
    "TEACHER_SUPERVISION_DATASET_VERSION",
    "annotation_template",
    "build_hard_negative_queue",
    "build_hard_negative_report",
    "build_runtime_training_bundle",
    "build_teacher_supervision_bundle",
    "example_weight",
    "is_ignored",
    "load_annotation_rows",
    "load_live_payloads",
    "lora_example_weight",
    "teacher_supervision_weight",
    "teacher_supervision_weight_components",
    "write_annotation_rows",
]


def __getattr__(name: str) -> Any:
    if name in _RUNTIME_EXPORTS:
        module = import_module(".runtime_training", __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name in _TEACHER_EXPORTS:
        module = import_module(".teacher_supervision", __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
