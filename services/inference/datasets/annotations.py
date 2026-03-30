from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


ANNOTATION_SCHEMA_PATH = Path(__file__).with_name("annotation_schema.json")
ANNOTATION_SCHEMA_MIGRATION_NOTES_PATH = Path(__file__).resolve().parents[2] / "docs" / "phase3c1_dataset_schema.md"


def load_annotation_schema() -> dict[str, Any]:
    return json.loads(ANNOTATION_SCHEMA_PATH.read_text(encoding="utf-8"))


ANNOTATION_SCHEMA_VERSION = str(load_annotation_schema().get("schemaVersion") or "2026-03-30")


@dataclass
class ClipAnnotation:
    clipId: str
    sourceDomain: str
    schemaVersion: str
    sourceRef: str | None
    eventFamily: str
    outcome: str
    shotSubtype: str | None
    ballVisible: bool
    hoopVisible: bool
    ballNearRim: float | None
    ballThroughHoopLikelihood: float | None
    possessionChangeLikelihood: float | None
    transitionLikelihood: float | None
    teacherConfidence: float | None
    humanVerified: bool
    reviewerNotes: str
    rawRuntimeOutputs: dict[str, Any] | None
    rawTeacherOutputs: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def annotation_template(*, clip_id: str, source_domain: str) -> ClipAnnotation:
    return ClipAnnotation(
        clipId=clip_id,
        sourceDomain=source_domain,
        schemaVersion=ANNOTATION_SCHEMA_VERSION,
        sourceRef=None,
        eventFamily="other",
        outcome="uncertain",
        shotSubtype=None,
        ballVisible=False,
        hoopVisible=False,
        ballNearRim=0.0,
        ballThroughHoopLikelihood=0.0,
        possessionChangeLikelihood=0.0,
        transitionLikelihood=0.0,
        teacherConfidence=None,
        humanVerified=False,
        reviewerNotes="",
        rawRuntimeOutputs={},
        rawTeacherOutputs=None,
    )


def load_annotation_rows(path: Path) -> list[ClipAnnotation]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON array at {path}.")
    return [ClipAnnotation(**_normalize_row(item)) for item in payload]


def write_annotation_rows(path: Path, rows: Iterable[ClipAnnotation | dict[str, Any]]) -> None:
    normalized_rows = [
        _normalize_row(row.to_dict() if isinstance(row, ClipAnnotation) else row)
        for row in rows
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized_rows, indent=2, sort_keys=True), encoding="utf-8")


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    required_fields = {
        "clipId",
        "sourceDomain",
        "schemaVersion",
        "eventFamily",
        "outcome",
        "shotSubtype",
        "ballVisible",
        "hoopVisible",
        "ballNearRim",
        "ballThroughHoopLikelihood",
        "possessionChangeLikelihood",
        "transitionLikelihood",
        "teacherConfidence",
        "humanVerified",
        "reviewerNotes",
        "rawRuntimeOutputs",
        "rawTeacherOutputs",
    }
    optional_fields = {"sourceRef"}
    normalized = dict(row)
    normalized["schemaVersion"] = str(normalized.get("schemaVersion") or ANNOTATION_SCHEMA_VERSION)
    missing = sorted(required_fields.difference(normalized))
    if missing:
        raise ValueError(f"Annotation row is missing required fields: {', '.join(missing)}")
    extras = sorted(set(row).difference(required_fields).difference(optional_fields))
    if extras:
        raise ValueError(f"Annotation row contains unsupported fields: {', '.join(extras)}")

    normalized["clipId"] = str(normalized["clipId"])
    normalized["sourceDomain"] = str(normalized["sourceDomain"])
    normalized["sourceRef"] = None if normalized.get("sourceRef") is None else str(normalized["sourceRef"])
    normalized["eventFamily"] = str(normalized["eventFamily"])
    normalized["outcome"] = str(normalized["outcome"])
    normalized["shotSubtype"] = None if normalized["shotSubtype"] is None else str(normalized["shotSubtype"])
    normalized["ballVisible"] = bool(normalized["ballVisible"])
    normalized["hoopVisible"] = bool(normalized["hoopVisible"])
    normalized["ballNearRim"] = _clamp_optional_probability(normalized["ballNearRim"], "ballNearRim")
    normalized["ballThroughHoopLikelihood"] = _clamp_optional_probability(
        normalized["ballThroughHoopLikelihood"],
        "ballThroughHoopLikelihood",
    )
    normalized["possessionChangeLikelihood"] = _clamp_optional_probability(
        normalized["possessionChangeLikelihood"],
        "possessionChangeLikelihood",
    )
    normalized["transitionLikelihood"] = _clamp_optional_probability(
        normalized["transitionLikelihood"],
        "transitionLikelihood",
    )
    normalized["teacherConfidence"] = _clamp_optional_probability(normalized["teacherConfidence"], "teacherConfidence")
    normalized["humanVerified"] = bool(normalized["humanVerified"])
    normalized["reviewerNotes"] = str(normalized["reviewerNotes"])
    normalized["rawRuntimeOutputs"] = _coerce_optional_mapping(normalized["rawRuntimeOutputs"], "rawRuntimeOutputs")
    normalized["rawTeacherOutputs"] = _coerce_optional_mapping(normalized["rawTeacherOutputs"], "rawTeacherOutputs")
    return normalized


def _clamp_optional_probability(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric.") from exc
    if parsed < 0.0 or parsed > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0.")
    return parsed


def _coerce_optional_mapping(value: Any, field_name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object.")
    return value
