from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any, Iterable

from .annotations import ANNOTATION_SCHEMA_VERSION, load_annotation_rows


TEACHER_SUPERVISION_DATASET_VERSION = "teacher-supervision-v1"
TEACHER_SUPERVISION_OUTPUT_DIR_NAME = "teacher_supervision"
SOURCE_SET_FILES = {
    "gold_set": "gold_set.json",
    "silver_set": "silver_set.json",
    "disagreement_queue": "disagreement_queue.jsonl",
}


@dataclass(frozen=True)
class TeacherSupervisionRecord:
    clipId: str
    sourceDomain: str
    sourceKind: str
    sourceSet: str
    schemaVersion: str
    split: str
    supervisionRole: str
    trainingEligible: bool
    calibrationAnchor: bool
    selectedLabelSource: str | None
    weight: float
    baseWeight: float
    hardExampleSignal: float
    hardExampleMultiplier: float
    teacherConfidence: float | None
    humanVerified: bool
    sourceRef: str | None
    reviewerNotes: str
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
    rawRuntimeOutputs: dict[str, Any]
    rawTeacherOutputs: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "clipId": self.clipId,
            "sourceDomain": self.sourceDomain,
            "sourceKind": self.sourceKind,
            "sourceSet": self.sourceSet,
            "schemaVersion": self.schemaVersion,
            "split": self.split,
            "supervisionRole": self.supervisionRole,
            "trainingEligible": self.trainingEligible,
            "calibrationAnchor": self.calibrationAnchor,
            "selectedLabelSource": self.selectedLabelSource,
            "weight": round(self.weight, 4),
            "baseWeight": round(self.baseWeight, 4),
            "hardExampleSignal": round(self.hardExampleSignal, 4),
            "hardExampleMultiplier": round(self.hardExampleMultiplier, 4),
            "teacherConfidence": self.teacherConfidence,
            "humanVerified": self.humanVerified,
            "sourceRef": self.sourceRef,
            "reviewerNotes": self.reviewerNotes,
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
            "rawRuntimeOutputs": self.rawRuntimeOutputs,
            "rawTeacherOutputs": self.rawTeacherOutputs,
        }


def build_teacher_supervision_bundle(
    repo_root: Path,
    output_dir: Path,
    *,
    min_teacher_confidence: float = 0.82,
    min_hard_negative_confidence: float = 0.55,
) -> dict[str, Any]:
    records = _load_seed_records(repo_root)
    supervision_records: list[TeacherSupervisionRecord] = []
    for record in records:
        supervision_records.append(
            _build_supervision_record(
                record,
                repo_root=repo_root,
                min_teacher_confidence=min_teacher_confidence,
                min_hard_negative_confidence=min_hard_negative_confidence,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    split_summary: dict[str, int] = {}
    for split_name in ("train", "val", "test"):
        split_rows = [record for record in supervision_records if record.split == split_name]
        split_summary[split_name] = len(split_rows)
        _write_jsonl(output_dir / split_name / "records.jsonl", (row.to_dict() for row in split_rows))

    _write_jsonl(output_dir / "all_records.jsonl", (row.to_dict() for row in supervision_records))
    _write_json(
        output_dir / "manifest.json",
        {
            "datasetVersion": TEACHER_SUPERVISION_DATASET_VERSION,
            "schemaVersion": ANNOTATION_SCHEMA_VERSION,
            "summary": _summarize_records(supervision_records),
            "splits": split_summary,
            "weightRules": {
                "goldBaseWeight": 1.35,
                "silverHighConfidenceMin": min_teacher_confidence,
                "silverMediumConfidenceMin": min_teacher_confidence - 0.08,
                "hardNegativeMinConfidence": min_hard_negative_confidence,
            },
        },
    )
    _write_json(
        output_dir / "weights.json",
        {
            "datasetVersion": TEACHER_SUPERVISION_DATASET_VERSION,
            "records": [
                {
                    "clipId": record.clipId,
                    "selectedLabelSource": record.selectedLabelSource,
                    "weight": round(record.weight, 4),
                    "baseWeight": round(record.baseWeight, 4),
                    "hardExampleSignal": round(record.hardExampleSignal, 4),
                    "hardExampleMultiplier": round(record.hardExampleMultiplier, 4),
                }
                for record in supervision_records
            ],
        },
    )
    return {
        "datasetVersion": TEACHER_SUPERVISION_DATASET_VERSION,
        "schemaVersion": ANNOTATION_SCHEMA_VERSION,
        "summary": _summarize_records(supervision_records),
        "splits": split_summary,
        "path": str(output_dir / "all_records.jsonl"),
        "manifestPath": str(output_dir / "manifest.json"),
        "weightsPath": str(output_dir / "weights.json"),
    }


def teacher_supervision_weight(
    row: dict[str, Any],
    *,
    min_teacher_confidence: float = 0.82,
    min_hard_negative_confidence: float = 0.55,
) -> float:
    base_weight, _, _, _, _ = _weight_components(
        row,
        min_teacher_confidence=min_teacher_confidence,
        min_hard_negative_confidence=min_hard_negative_confidence,
    )
    return round(base_weight, 4)


def teacher_supervision_weight_components(
    row: dict[str, Any],
    *,
    min_teacher_confidence: float = 0.82,
    min_hard_negative_confidence: float = 0.55,
) -> dict[str, Any]:
    base_weight, role, selected_source, hard_signal, hard_multiplier = _weight_components(
        row,
        min_teacher_confidence=min_teacher_confidence,
        min_hard_negative_confidence=min_hard_negative_confidence,
    )
    return {
        "weight": round(base_weight, 4),
        "supervisionRole": role,
        "selectedLabelSource": selected_source,
        "hardExampleSignal": round(hard_signal, 4),
        "hardExampleMultiplier": round(hard_multiplier, 4),
    }


def _build_supervision_record(
    record: dict[str, Any],
    *,
    repo_root: Path,
    min_teacher_confidence: float,
    min_hard_negative_confidence: float,
) -> TeacherSupervisionRecord:
    row = dict(record)
    if row.get("sourceRef") is None:
        row["sourceRef"] = _fallback_source_ref(row, repo_root=repo_root)

    base_weight, role, selected_source, hard_signal, hard_multiplier = _weight_components(
        row,
        min_teacher_confidence=min_teacher_confidence,
        min_hard_negative_confidence=min_hard_negative_confidence,
    )
    teacher_confidence = _optional_float(row.get("teacherConfidence"))
    training_eligible = base_weight > 0.0 and role != "ignored"
    calibration_anchor = row["sourceKind"] == "gold" and row["split"] in {"val", "test"}
    gold_event_family, gold_outcome, gold_shot_subtype = _gold_label(row)
    teacher_event_family, teacher_outcome, teacher_shot_subtype = _teacher_label(row)
    selected_event_family, selected_outcome, selected_shot_subtype = _selected_label(
        row,
        selected_source=selected_source,
        gold_label=(gold_event_family, gold_outcome, gold_shot_subtype),
        teacher_label=(teacher_event_family, teacher_outcome, teacher_shot_subtype),
    )
    selected_display_label = None
    if selected_event_family is not None and selected_outcome is not None:
        selected_display_label = _derive_display_label(
            event_family=selected_event_family,
            outcome=selected_outcome,
            shot_subtype=selected_shot_subtype,
        )

    return TeacherSupervisionRecord(
        clipId=str(row["clipId"]),
        sourceDomain=str(row["sourceDomain"]),
        sourceKind=str(row["sourceKind"]),
        sourceSet=str(row["sourceSet"]),
        schemaVersion=str(row["schemaVersion"]),
        split=str(row["split"]),
        supervisionRole=role,
        trainingEligible=training_eligible,
        calibrationAnchor=calibration_anchor,
        selectedLabelSource=selected_source,
        weight=base_weight,
        baseWeight=_base_weight(row),
        hardExampleSignal=hard_signal,
        hardExampleMultiplier=hard_multiplier,
        teacherConfidence=teacher_confidence,
        humanVerified=bool(row.get("humanVerified", False)),
        sourceRef=_optional_text(row.get("sourceRef")),
        reviewerNotes=str(row.get("reviewerNotes") or ""),
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
        rawRuntimeOutputs=dict(row.get("rawRuntimeOutputs") or {}),
        rawTeacherOutputs=dict(row.get("rawTeacherOutputs") or {}) or None,
    )


def _load_seed_records(repo_root: Path) -> list[dict[str, Any]]:
    dataset_dir = repo_root / "services" / "inference" / "datasets"
    records: list[dict[str, Any]] = []
    for source_set, filename in SOURCE_SET_FILES.items():
        path = dataset_dir / filename
        if filename.endswith(".jsonl"):
            rows = _read_jsonl(path)
        else:
            rows = [row.to_dict() for row in load_annotation_rows(path)]
        for raw_row in rows:
            records.append(_normalize_seed_record(raw_row, source_set=source_set))
    return records


def _normalize_seed_record(raw_row: dict[str, Any], *, source_set: str) -> dict[str, Any]:
    record = dict(raw_row)
    record["schemaVersion"] = str(record.get("schemaVersion") or ANNOTATION_SCHEMA_VERSION)
    if record["schemaVersion"] != ANNOTATION_SCHEMA_VERSION:
        raise ValueError(f"unexpected schemaVersion for {record.get('clipId')}: {record['schemaVersion']}")
    record["sourceSet"] = source_set
    record["sourceKind"] = str(record.get("sourceKind") or _default_source_kind(source_set))
    record["sourceDomain"] = str(record.get("sourceDomain") or source_set)
    record["sourceRef"] = _optional_text(record.get("sourceRef"))
    record["shotSubtype"] = _optional_text(record.get("shotSubtype"))
    record["teacherConfidence"] = _optional_float(record.get("teacherConfidence"))
    record["split"] = _assign_split(record)
    return record


def _assign_split(record: dict[str, Any]) -> str:
    bucket = _stable_bucket(str(record["clipId"]))
    source_kind = str(record["sourceKind"])
    source_domain = str(record["sourceDomain"])
    if source_kind == "gold":
        return "val" if bucket < 55 else "test"
    if source_kind == "disagreement":
        if bucket < 70:
            return "train"
        if bucket < 85:
            return "val"
        return "test"
    if source_domain == "hard_negative":
        if bucket < 80:
            return "train"
        if bucket < 92:
            return "val"
        return "test"
    if source_kind == "silver":
        if bucket < 72:
            return "train"
        if bucket < 88:
            return "val"
        return "test"
    return "train" if bucket < 80 else "val"


def _weight_components(
    row: dict[str, Any],
    *,
    min_teacher_confidence: float,
    min_hard_negative_confidence: float,
) -> tuple[float, str, str | None, float, float]:
    source_kind = str(row.get("sourceKind") or "silver")
    source_domain = str(row.get("sourceDomain") or "")
    teacher_confidence = _optional_float(row.get("teacherConfidence"))
    hard_signal = _hard_example_signal(
        row,
        source_kind=source_kind,
        source_domain=source_domain,
        teacher_confidence=teacher_confidence,
        reasons=_reason_tokens(row),
    )
    role = "ignored"
    selected_source: str | None = None
    base_weight = 0.0

    if source_kind == "gold":
        role = "gold_anchor"
        selected_source = "gold"
        base_weight = 1.35
    elif source_domain == "hard_negative":
        role = "hard_negative"
        selected_source = "teacher"
        if teacher_confidence is not None and teacher_confidence >= min_hard_negative_confidence:
            base_weight = 0.55
        else:
            base_weight = 0.35
    elif source_kind == "disagreement":
        role = "teacher_distill"
        selected_source = "teacher"
        if teacher_confidence is not None and teacher_confidence >= min_teacher_confidence:
            base_weight = 0.82
        elif teacher_confidence is not None and teacher_confidence >= max(min_teacher_confidence - 0.08, 0.7):
            base_weight = 0.62
        else:
            base_weight = 0.0
    elif source_kind == "silver":
        role = "teacher_distill"
        selected_source = "teacher"
        if teacher_confidence is not None and teacher_confidence >= min_teacher_confidence:
            base_weight = 0.85
        elif teacher_confidence is not None and teacher_confidence >= max(min_teacher_confidence - 0.08, 0.7):
            base_weight = 0.65
        else:
            base_weight = 0.0

    hard_multiplier = 1.0 + 0.55 * hard_signal
    final_weight = base_weight * hard_multiplier
    if final_weight <= 0.0:
        return 0.0, "ignored", None, hard_signal, hard_multiplier
    return final_weight, role, selected_source, hard_signal, hard_multiplier


def _gold_label(row: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    if str(row.get("sourceKind")) != "gold":
        return None, None, None
    return (
        _optional_text(row.get("eventFamily")),
        _optional_text(row.get("outcome")),
        _optional_text(row.get("shotSubtype")),
    )


def _teacher_label(row: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    outputs = dict(row.get("rawTeacherOutputs") or {})
    if not outputs:
        return None, None, None
    return (
        _optional_text(outputs.get("eventFamily") or row.get("eventFamily")),
        _optional_text(outputs.get("outcome") or row.get("outcome")),
        _optional_text(outputs.get("shotSubtype") or row.get("shotSubtype")),
    )


def _selected_label(
    row: dict[str, Any],
    *,
    selected_source: str | None,
    gold_label: tuple[str | None, str | None, str | None],
    teacher_label: tuple[str | None, str | None, str | None],
) -> tuple[str | None, str | None, str | None]:
    if selected_source == "gold":
        return gold_label
    if selected_source == "teacher":
        return teacher_label
    return None, None, None


def _base_weight(row: dict[str, Any]) -> float:
    source_kind = str(row.get("sourceKind") or "")
    teacher_confidence = _optional_float(row.get("teacherConfidence"))
    if source_kind == "gold":
        return 1.35
    if source_kind == "disagreement":
        if teacher_confidence is not None and teacher_confidence >= 0.82:
            return 0.82
        if teacher_confidence is not None and teacher_confidence >= 0.74:
            return 0.62
        return 0.0
    if source_kind == "silver":
        if teacher_confidence is not None and teacher_confidence >= 0.82:
            return 0.85
        if teacher_confidence is not None and teacher_confidence >= 0.74:
            return 0.65
        return 0.0
    if str(row.get("sourceDomain") or "") == "hard_negative":
        if teacher_confidence is not None and teacher_confidence >= 0.55:
            return 0.55
        return 0.35
    return 0.0


def _reason_tokens(row: dict[str, Any]) -> list[str]:
    runtime = dict(row.get("rawRuntimeOutputs") or {})
    teacher = dict(row.get("rawTeacherOutputs") or {})
    tokens: list[str] = []
    for payload in (runtime, teacher):
        for key, value in payload.items():
            if key.startswith("reason=") and value:
                tokens.append(key.removeprefix("reason="))
    if str(row.get("sourceKind")) == "disagreement":
        tokens.append("runtime teacher disagree")
    if str(row.get("sourceDomain")) == "hard_negative":
        tokens.append("hard negative")
    if row.get("humanVerified"):
        tokens.append("human verified")
    return tokens


def _summarize_records(records: list[TeacherSupervisionRecord]) -> dict[str, Any]:
    return {
        "totalRecords": len(records),
        "byRole": dict(sorted(Counter(record.supervisionRole for record in records).items())),
        "bySourceKind": dict(sorted(Counter(record.sourceKind for record in records).items())),
        "bySourceDomain": dict(sorted(Counter(record.sourceDomain for record in records).items())),
        "trainingEligibleRecords": sum(1 for record in records if record.trainingEligible),
        "calibrationAnchorRecords": sum(1 for record in records if record.calibrationAnchor),
        "teacherSeparatedRecords": sum(
            1
            for record in records
            if record.goldEventFamily is not None and record.teacherEventFamily is not None and record.selectedLabelSource == "gold"
        ),
    }


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object rows in {path}.")
        rows.append(payload)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stable_bucket(value: str) -> int:
    return int(sha1(value.encode("utf-8")).hexdigest()[:8], 16) % 100


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _default_source_kind(source_set: str) -> str:
    if source_set == "gold_set":
        return "gold"
    if source_set == "silver_set":
        return "silver"
    return "disagreement"


def _fallback_source_ref(row: dict[str, Any], *, repo_root: Path) -> str:
    del repo_root
    outcome = str(row.get("outcome") or "uncertain")
    if outcome == "made":
        return "backend/.external/HoopCut_FH/main/static/clips/make_2_3.20s.mp4"
    if outcome == "missed":
        return "backend/.external/HoopCut_FH/main/static/clips/miss_2_3.13s.mp4"
    return "backend/.external/HoopCut_FH/main/static/clips/miss_1_0.00s.mp4"


def _hard_example_signal(
    row: dict[str, Any],
    *,
    source_kind: str | None = None,
    source_domain: str | None = None,
    teacher_confidence: float | None = None,
    reasons: Iterable[str] = (),
) -> float:
    signal = 0.0
    kind = _normalize_text(source_kind)
    domain = _normalize_text(source_domain)
    reason_set = {_normalize_text(reason) for reason in reasons if _normalize_text(reason)}

    if row is not None:
        kind = kind or _normalize_text(row.get("sourceKind"))
        domain = domain or _normalize_text(row.get("sourceDomain"))
        teacher_confidence = _first_float(row, "teacherConfidence", "teacher_confidence", default=teacher_confidence)
        reason_set |= _row_reason_set(row)

    if kind == "disagreement":
        signal += 0.45
    if domain == "hard negative" or (domain and "hard negative" in domain):
        signal += 0.3
    if teacher_confidence is not None and teacher_confidence >= 0.9:
        signal += 0.15
    if reason_set & {"hard negative", "runtime teacher disagree", "miss vs made conflict", "app facing label only highlight"}:
        signal += 0.25
    if "miss" in reason_set and "made" in reason_set:
        signal += 0.1
    return min(max(signal, 0.0), 1.0)


def _row_reason_set(row: dict[str, Any]) -> set[str]:
    reasons: set[str] = set()
    features = row.get("features")
    if isinstance(features, dict):
        for key in features:
            if key.startswith("reason="):
                normalized = _normalize_text(key.removeprefix("reason="))
                if normalized:
                    reasons.add(normalized)
    if isinstance(row.get("priorityReasons"), (list, tuple, set)):
        for reason in row["priorityReasons"]:
            normalized = _normalize_text(reason)
            if normalized:
                reasons.add(normalized)
    if isinstance(row.get("reasons"), (list, tuple, set)):
        for reason in row["reasons"]:
            normalized = _normalize_text(reason)
            if normalized:
                reasons.add(normalized)
    return reasons


def _first_float(row: dict[str, Any], *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        if key in row and row[key] is not None:
            try:
                return float(row[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be numeric.") from exc
    return default


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    return text or None


def _derive_display_label(
    *,
    event_family: str,
    outcome: str,
    shot_subtype: str | None,
) -> str:
    if event_family == "turnover":
        return "Steal"
    if event_family == "transition":
        return "Fast Break"
    if event_family == "defensive_event":
        return "Block" if outcome == "blocked" else "Highlight"
    if event_family != "shot_attempt":
        return "Highlight"
    if outcome == "missed":
        return "Highlight"
    if outcome == "blocked":
        return "Block"
    if shot_subtype == "dunk" and outcome == "made":
        return "Dunk"
    if shot_subtype == "layup" and outcome == "made":
        return "Layup"
    if shot_subtype == "three" and outcome == "made":
        return "Three Pointer"
    if shot_subtype == "putback" and outcome == "made":
        return "Made Shot"
    if outcome == "made":
        return "Made Shot"
    return "Highlight"
