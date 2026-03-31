from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Sequence

from .annotations import ANNOTATION_SCHEMA_VERSION, ClipAnnotation, _normalize_row, load_annotation_rows


PSEUDO_LABEL_DATASET_VERSION = "phase4-pseudo-label-v1"
PSEUDO_LABEL_OUTPUT_DIR_NAME = "phase4_pseudo_labels"
DEFAULT_MIN_TEACHER_CONFIDENCE = 0.82
DEFAULT_SOURCE_DOMAINS = (
    "live_shadow",
    "live_runtime",
    "live_staging",
    "staging_smoke",
    "manual_negative",
    "hard_negative",
)
DEFAULT_INPUT_FILES = (
    "gold_set.json",
    "silver_set.json",
)


@dataclass(frozen=True)
class Phase4PseudoLabelRecord:
    clipId: str
    sourceDomain: str
    sourceKind: str
    sourceSet: str
    sourceRef: str | None
    schemaVersion: str
    split: str
    recordType: str
    humanVerified: bool
    teacherConfidence: float | None
    confidenceGatePassed: bool
    trainingEligible: bool
    selectedLabelSource: str
    gateReason: str
    goldEventFamily: str | None
    goldOutcome: str | None
    goldShotSubtype: str | None
    teacherEventFamily: str | None
    teacherOutcome: str | None
    teacherShotSubtype: str | None
    selectedEventFamily: str | None
    selectedOutcome: str | None
    selectedShotSubtype: str | None
    selectedDisplayLabel: str | None
    reviewerNotes: str
    rawRuntimeOutputs: dict[str, Any]
    rawTeacherOutputs: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "clipId": self.clipId,
            "sourceDomain": self.sourceDomain,
            "sourceKind": self.sourceKind,
            "sourceSet": self.sourceSet,
            "sourceRef": self.sourceRef,
            "schemaVersion": self.schemaVersion,
            "split": self.split,
            "recordType": self.recordType,
            "humanVerified": self.humanVerified,
            "teacherConfidence": self.teacherConfidence,
            "confidenceGatePassed": self.confidenceGatePassed,
            "trainingEligible": self.trainingEligible,
            "selectedLabelSource": self.selectedLabelSource,
            "gateReason": self.gateReason,
            "goldEventFamily": self.goldEventFamily,
            "goldOutcome": self.goldOutcome,
            "goldShotSubtype": self.goldShotSubtype,
            "teacherEventFamily": self.teacherEventFamily,
            "teacherOutcome": self.teacherOutcome,
            "teacherShotSubtype": self.teacherShotSubtype,
            "selectedEventFamily": self.selectedEventFamily,
            "selectedOutcome": self.selectedOutcome,
            "selectedShotSubtype": self.selectedShotSubtype,
            "selectedDisplayLabel": self.selectedDisplayLabel,
            "reviewerNotes": self.reviewerNotes,
            "rawRuntimeOutputs": self.rawRuntimeOutputs,
            "rawTeacherOutputs": self.rawTeacherOutputs,
        }


def build_phase4_pseudo_label_bundle(
    repo_root: Path,
    output_dir: Path,
    *,
    input_paths: Sequence[Path] | None = None,
    min_teacher_confidence: float = DEFAULT_MIN_TEACHER_CONFIDENCE,
    source_domains: Sequence[str] = DEFAULT_SOURCE_DOMAINS,
) -> dict[str, Any]:
    loaded_inputs = _load_input_annotations(repo_root, input_paths=input_paths)
    allowed_source_domains = {str(domain).strip() for domain in source_domains if str(domain).strip()}

    records: list[Phase4PseudoLabelRecord] = []
    for input_path, annotations in loaded_inputs:
        source_set = input_path.stem
        for annotation in annotations:
            records.append(
                _build_record(
                    annotation,
                    source_set=source_set,
                    min_teacher_confidence=min_teacher_confidence,
                    allowed_source_domains=allowed_source_domains,
                )
            )

    gold_anchor_records = [record for record in records if record.recordType == "gold_anchor"]
    pseudo_label_records = [record for record in records if record.recordType == "pseudo_label"]
    filtered_records = [record for record in records if record.recordType == "filtered"]
    split_summary = Counter(record.split for record in records)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "all_records.jsonl", (record.to_dict() for record in records))
    _write_jsonl(output_dir / "gold_anchor_records.jsonl", (record.to_dict() for record in gold_anchor_records))
    _write_jsonl(output_dir / "pseudo_label_records.jsonl", (record.to_dict() for record in pseudo_label_records))
    _write_jsonl(output_dir / "filtered_records.jsonl", (record.to_dict() for record in filtered_records))

    manifest = {
        "datasetVersion": PSEUDO_LABEL_DATASET_VERSION,
        "schemaVersion": ANNOTATION_SCHEMA_VERSION,
        "sourceDomainFilter": sorted(allowed_source_domains),
        "sourceFiles": [str(path) for path, _ in loaded_inputs],
        "summary": {
            "totalRecords": len(records),
            "goldAnchorRecords": len(gold_anchor_records),
            "pseudoLabelRecords": len(pseudo_label_records),
            "filteredRecords": len(filtered_records),
            "trainingEligibleRecords": len(pseudo_label_records),
            "teacherSeparatedRecords": sum(
                1
                for record in gold_anchor_records
                if record.teacherEventFamily is not None or record.teacherOutcome is not None or record.teacherShotSubtype is not None
            ),
            "splits": dict(sorted(split_summary.items())),
            "byRecordType": dict(sorted(Counter(record.recordType for record in records).items())),
            "bySourceKind": dict(sorted(Counter(record.sourceKind for record in records).items())),
            "bySourceDomain": dict(sorted(Counter(record.sourceDomain for record in records).items())),
            "byGateReason": dict(sorted(Counter(record.gateReason for record in records if record.recordType != "pseudo_label").items())),
            "retainedTeacherConfidence": _confidence_summary(record.teacherConfidence for record in pseudo_label_records),
        },
        "selectionPolicy": {
            "minTeacherConfidence": round(float(min_teacher_confidence), 4),
            "sourceDomainFilter": sorted(allowed_source_domains),
            "teacherBackedOnly": True,
            "goldAnchorsSeparate": True,
            "productionTeacherCalls": False,
        },
        "files": {
            "allRecords": str(output_dir / "all_records.jsonl"),
            "goldAnchors": str(output_dir / "gold_anchor_records.jsonl"),
            "pseudoLabels": str(output_dir / "pseudo_label_records.jsonl"),
            "filtered": str(output_dir / "filtered_records.jsonl"),
        },
        "notes": [
            "Teacher outputs are consumed from stored annotations only; production inference never calls a teacher model.",
            "Gold anchors remain separate from retained pseudo-labels and are excluded from pseudo-label training outputs.",
            "Only confidence-gated, teacher-backed in-domain rows are retained in pseudo_label_records.jsonl.",
        ],
    }
    _write_json(output_dir / "manifest.json", manifest)
    return {
        "datasetVersion": PSEUDO_LABEL_DATASET_VERSION,
        "schemaVersion": ANNOTATION_SCHEMA_VERSION,
        "summary": manifest["summary"],
        "manifestPath": str(output_dir / "manifest.json"),
        "allRecordsPath": str(output_dir / "all_records.jsonl"),
        "goldAnchorsPath": str(output_dir / "gold_anchor_records.jsonl"),
        "pseudoLabelsPath": str(output_dir / "pseudo_label_records.jsonl"),
        "filteredPath": str(output_dir / "filtered_records.jsonl"),
    }


def load_phase4_pseudo_label_examples(
    repo_root: Path,
    *,
    input_paths: Sequence[Path] | None = None,
    min_teacher_confidence: float = DEFAULT_MIN_TEACHER_CONFIDENCE,
    source_domains: Sequence[str] = DEFAULT_SOURCE_DOMAINS,
) -> list[Phase4PseudoLabelRecord]:
    loaded_inputs = _load_input_annotations(repo_root, input_paths=input_paths)
    allowed_source_domains = {str(domain).strip() for domain in source_domains if str(domain).strip()}
    records: list[Phase4PseudoLabelRecord] = []
    for input_path, annotations in loaded_inputs:
        source_set = input_path.stem
        for annotation in annotations:
            records.append(
                _build_record(
                    annotation,
                    source_set=source_set,
                    min_teacher_confidence=min_teacher_confidence,
                    allowed_source_domains=allowed_source_domains,
                )
            )
    return records


def _load_input_annotations(
    repo_root: Path,
    *,
    input_paths: Sequence[Path] | None = None,
) -> list[tuple[Path, list[ClipAnnotation]]]:
    dataset_dir = repo_root / "services" / "inference" / "datasets"
    resolved_paths = list(input_paths or (dataset_dir / name for name in DEFAULT_INPUT_FILES))
    loaded: list[tuple[Path, list[ClipAnnotation]]] = []
    for path in resolved_paths:
        path = Path(path)
        if not path.exists():
            continue
        loaded.append((path, _load_annotation_file(path)))
    if not loaded:
        raise FileNotFoundError("No pseudo-label input files were found.")
    return loaded


def _load_annotation_file(path: Path) -> list[ClipAnnotation]:
    if path.suffix.lower() == ".jsonl":
        rows = [
            ClipAnnotation(**_normalize_row(json.loads(line)))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return rows
    return load_annotation_rows(path)


def _build_record(
    annotation: ClipAnnotation,
    *,
    source_set: str,
    min_teacher_confidence: float,
    allowed_source_domains: set[str],
) -> Phase4PseudoLabelRecord:
    source_kind = _infer_source_kind(annotation, source_set=source_set)
    teacher_outputs = dict(annotation.rawTeacherOutputs or {}) or None
    teacher_event_family = _optional_text((teacher_outputs or {}).get("eventFamily"))
    teacher_outcome = _optional_text((teacher_outputs or {}).get("outcome"))
    teacher_shot_subtype = _optional_text((teacher_outputs or {}).get("shotSubtype"))
    teacher_confidence = _teacher_confidence(annotation, teacher_outputs)
    source_domain_allowed = annotation.sourceDomain in allowed_source_domains if allowed_source_domains else True
    has_teacher_outputs = teacher_outputs is not None

    gold_event_family = annotation.eventFamily if annotation.humanVerified else None
    gold_outcome = annotation.outcome if annotation.humanVerified else None
    gold_shot_subtype = annotation.shotSubtype if annotation.humanVerified else None

    if annotation.humanVerified:
        record_type = "gold_anchor"
        selected_label_source = "gold"
        confidence_gate_passed = False
        training_eligible = False
        gate_reason = "gold_anchor_reserved"
        split = "calibration"
    else:
        split = _assign_split(annotation.clipId, annotation.sourceDomain, source_set)
        if not source_domain_allowed:
            record_type = "filtered"
            selected_label_source = "teacher"
            confidence_gate_passed = False
            training_eligible = False
            gate_reason = "outside_in_domain_slice"
        elif not has_teacher_outputs:
            record_type = "filtered"
            selected_label_source = "teacher"
            confidence_gate_passed = False
            training_eligible = False
            gate_reason = "missing_teacher_outputs"
        elif teacher_confidence is None:
            record_type = "filtered"
            selected_label_source = "teacher"
            confidence_gate_passed = False
            training_eligible = False
            gate_reason = "missing_teacher_confidence"
        elif teacher_confidence < min_teacher_confidence:
            record_type = "filtered"
            selected_label_source = "teacher"
            confidence_gate_passed = False
            training_eligible = False
            gate_reason = "below_confidence_gate"
        else:
            record_type = "pseudo_label"
            selected_label_source = "teacher"
            confidence_gate_passed = True
            training_eligible = True
            gate_reason = "retained"

    selected_event_family = annotation.eventFamily if selected_label_source == "gold" else teacher_event_family or annotation.eventFamily
    selected_outcome = annotation.outcome if selected_label_source == "gold" else teacher_outcome or annotation.outcome
    selected_shot_subtype = annotation.shotSubtype if selected_label_source == "gold" else teacher_shot_subtype or annotation.shotSubtype
    if selected_event_family is not None and selected_outcome is not None:
        _, selected_display_label = _derive_display_label(
            event_family=selected_event_family,
            outcome=selected_outcome,
            shot_subtype=selected_shot_subtype,
        )
    else:
        selected_display_label = None

    return Phase4PseudoLabelRecord(
        clipId=annotation.clipId,
        sourceDomain=annotation.sourceDomain,
        sourceKind=source_kind,
        sourceSet=source_set,
        sourceRef=annotation.sourceRef,
        schemaVersion=annotation.schemaVersion or ANNOTATION_SCHEMA_VERSION,
        split=split,
        recordType=record_type,
        humanVerified=annotation.humanVerified,
        teacherConfidence=teacher_confidence,
        confidenceGatePassed=confidence_gate_passed,
        trainingEligible=training_eligible,
        selectedLabelSource=selected_label_source,
        gateReason=gate_reason,
        goldEventFamily=gold_event_family,
        goldOutcome=gold_outcome,
        goldShotSubtype=gold_shot_subtype,
        teacherEventFamily=teacher_event_family,
        teacherOutcome=teacher_outcome,
        teacherShotSubtype=teacher_shot_subtype,
        selectedEventFamily=selected_event_family,
        selectedOutcome=selected_outcome,
        selectedShotSubtype=selected_shot_subtype,
        selectedDisplayLabel=selected_display_label,
        reviewerNotes=annotation.reviewerNotes,
        rawRuntimeOutputs=dict(annotation.rawRuntimeOutputs or {}),
        rawTeacherOutputs=teacher_outputs,
    )


def _infer_source_kind(annotation: ClipAnnotation, *, source_set: str) -> str:
    if annotation.humanVerified:
        return "gold"
    if source_set == "disagreement_queue":
        return "disagreement"
    return "teacher"


def _assign_split(clip_id: str, source_domain: str, source_set: str) -> str:
    digest = sha1(f"{clip_id}:{source_domain}:{source_set}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "val"
    return "test"


def _teacher_confidence(annotation: ClipAnnotation, teacher_outputs: dict[str, Any] | None) -> float | None:
    if annotation.teacherConfidence is not None:
        return float(annotation.teacherConfidence)
    if teacher_outputs and teacher_outputs.get("confidence") is not None:
        try:
            return float(teacher_outputs["confidence"])
        except (TypeError, ValueError):
            return None
    return None


def _derive_display_label(*, event_family: str, outcome: str, shot_subtype: str | None) -> tuple[str, str]:
    if event_family == "turnover":
        return "steal", "Steal"
    if event_family == "transition":
        return "fast break", "Fast Break"
    if event_family == "defensive_event":
        return ("block", "Block") if outcome == "blocked" else ("uncertain", "Highlight")
    if event_family != "shot_attempt":
        return "uncertain", "Highlight"

    if outcome == "missed":
        return "miss", "Highlight"
    if outcome == "blocked":
        return "block", "Block"
    if shot_subtype == "dunk" and outcome == "made":
        return "dunk", "Dunk"
    if shot_subtype == "layup" and outcome == "made":
        return "layup", "Layup"
    if shot_subtype == "three" and outcome == "made":
        return "three", "Three Pointer"
    if shot_subtype == "putback" and outcome == "made":
        return "putback", "Made Shot"
    if outcome == "made":
        return shot_subtype or "jumper", "Made Shot"
    return shot_subtype or "uncertain", "Highlight"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _confidence_summary(values: Iterable[float | None]) -> dict[str, float | None]:
    parsed = [float(value) for value in values if value is not None]
    if not parsed:
        return {"min": None, "mean": None, "max": None}
    return {
        "min": round(min(parsed), 4),
        "mean": round(mean(parsed), 4),
        "max": round(max(parsed), 4),
    }


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True))
            handle.write("\n")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
