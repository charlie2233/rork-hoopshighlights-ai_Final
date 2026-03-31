from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from statistics import mean
from typing import Any


ANNOTATION_SCHEMA_VERSION = "2026-03-31"
ANNOTATION_SCHEMA_PATH = Path(__file__).with_name("annotation_schema.json")
SOURCE_SET_FILES = {
    "gold": "gold_set.json",
    "silver": "silver_set.json",
    "disagreement": "disagreement_queue.jsonl",
}


@dataclass(frozen=True)
class RuntimeRecord:
    clipId: str
    sourceDomain: str
    sourceKind: str
    eventFamily: str
    outcome: str
    shotSubtype: str | None
    ballVisible: bool
    hoopVisible: bool
    ballNearRim: float
    ballThroughHoopLikelihood: float
    possessionChangeLikelihood: float
    transitionLikelihood: float
    teacherConfidence: float
    humanVerified: bool
    reviewerNotes: str
    rawRuntimeOutputs: dict[str, Any]
    rawTeacherOutputs: dict[str, Any]
    schemaVersion: str = ANNOTATION_SCHEMA_VERSION


def _read_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")


def _required_fields() -> set[str]:
    schema = json.loads(ANNOTATION_SCHEMA_PATH.read_text())
    return set(schema["required"])


def _validate_record(record: dict[str, Any]) -> None:
    missing = _required_fields() - set(record)
    if missing:
        raise ValueError(f"annotation record missing fields: {sorted(missing)}")
    if record.get("schemaVersion") != ANNOTATION_SCHEMA_VERSION:
        raise ValueError(f"unexpected schemaVersion for {record.get('clipId')}: {record.get('schemaVersion')}")


def _stable_bucket(clip_id: str) -> int:
    return int(sha1(clip_id.encode("utf-8")).hexdigest()[:8], 16) % 100


def _gate_silver(record: dict[str, Any]) -> tuple[bool, float, str]:
    source_domain = str(record.get("sourceDomain") or "")
    source_kind = str(record.get("sourceKind") or "silver")
    teacher_conf = float(record.get("teacherConfidence") or 0.0)
    runtime_conf = float((record.get("rawRuntimeOutputs") or {}).get("confidence") or 0.0)
    if source_kind == "gold":
        return True, 1.5, "gold_anchor"
    if source_domain == "hard_negative":
        if teacher_conf >= 0.55 or runtime_conf >= 0.45:
            return True, 0.7, "hard_negative"
        return False, 0.0, "hard_negative_low_signal"
    if source_kind == "disagreement":
        return True, 1.05 if teacher_conf >= 0.8 else 0.9, "disagreement_queue"
    if teacher_conf >= 0.9 and runtime_conf >= 0.65:
        return True, 0.85, "high_confidence_silver"
    if teacher_conf >= 0.8 and runtime_conf >= 0.55:
        return True, 0.6, "medium_confidence_silver"
    return False, 0.0, "confidence_gate"


def _assign_split(record: dict[str, Any]) -> str:
    bucket = _stable_bucket(str(record["clipId"]))
    source_kind = str(record.get("sourceKind") or "silver")
    if source_kind == "gold":
        return "val" if bucket < 55 else "test"
    if source_kind == "disagreement":
        if bucket < 68:
            return "train"
        if bucket < 84:
            return "val"
        return "test"
    if str(record.get("sourceDomain") or "") == "hard_negative":
        if bucket < 78:
            return "train"
        if bucket < 90:
            return "val"
        return "test"
    if bucket < 82:
        return "train"
    if bucket < 92:
        return "val"
    return "test"


def _feature_row(record: dict[str, Any]) -> dict[str, float]:
    runtime = record.get("rawRuntimeOutputs") or {}
    teacher = record.get("rawTeacherOutputs") or {}
    features: dict[str, float] = {
        "ballVisible": 1.0 if record.get("ballVisible") else 0.0,
        "hoopVisible": 1.0 if record.get("hoopVisible") else 0.0,
        "ballNearRim": float(record.get("ballNearRim") or 0.0),
        "ballThroughHoopLikelihood": float(record.get("ballThroughHoopLikelihood") or 0.0),
        "possessionChangeLikelihood": float(record.get("possessionChangeLikelihood") or 0.0),
        "transitionLikelihood": float(record.get("transitionLikelihood") or 0.0),
        "runtimeConfidence": float(runtime.get("confidence") or 0.0),
        "teacherConfidence": float(record.get("teacherConfidence") or 0.0),
    }
    for prefix, payload in (("runtime", runtime), ("teacher", teacher)):
        if not isinstance(payload, dict):
            continue
        for key in ("eventFamily", "outcome", "shotSubtype", "label"):
            value = payload.get(key)
            if value is None:
                continue
            features[f"{prefix}{key[0].upper() + key[1:]}={value}"] = 1.0
    features[f"sourceDomain={record.get('sourceDomain')}"] = 1.0
    features[f"sourceKind={record.get('sourceKind')}"] = 1.0
    features[f"humanVerified={bool(record.get('humanVerified'))}"] = 1.0
    return features


def _active_target(record: dict[str, Any]) -> bool:
    active, _, _ = _gate_silver(record)
    return active


def _load_seed_records(repo_root: Path) -> list[dict[str, Any]]:
    datasets_dir = repo_root / "services" / "inference" / "datasets"
    records: list[dict[str, Any]] = []
    for filename in SOURCE_SET_FILES.values():
        path = datasets_dir / filename
        records.extend(_read_json(path) if path.suffix == ".json" else _read_jsonl(path))
    for record in records:
        _validate_record(record)
    return records


def build_runtime_training_bundle(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    records = _load_seed_records(repo_root)
    splits: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": [], "ignored": []}
    source_domain_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    gated_silver = 0

    for record in records:
        split = _assign_split(record)
        active, weight, gate_reason = _gate_silver(record)
        expanded = {
            **record,
            "featureVersion": "runtime-fusion-v2",
            "features": _feature_row(record),
            "ignored": not active,
            "split": split,
            "weight": weight,
            "gateReason": gate_reason,
        }
        source_domain_counts[str(record.get("sourceDomain") or "unknown")] += 1
        class_counts[str(record.get("eventFamily") or "unknown")] += 1
        if active:
            splits[split].append(expanded)
            if record.get("sourceKind") == "silver":
                gated_silver += 1
        else:
            splits["ignored"].append(expanded)

    feature_names = sorted({name for split_rows in splits.values() for row in split_rows for name in row["features"]})
    lora_rows = [row for row in splits["train"] if row["weight"] >= 0.6 and not row["ignored"]]
    output_dir.mkdir(parents=True, exist_ok=True)
    for split_name in ("train", "val", "test"):
        _write_jsonl(output_dir / split_name / "records.jsonl", splits[split_name])
    _write_jsonl(output_dir / "ignored.jsonl", splits["ignored"])
    _write_json(output_dir / "feature_names.json", feature_names)
    _write_jsonl(output_dir / "videomae_lora_v1" / "records.jsonl", lora_rows)

    manifest = {
        "schemaVersion": ANNOTATION_SCHEMA_VERSION,
        "summary": {
            "totalRecords": len(records),
            "activeRecords": sum(len(rows) for key, rows in splits.items() if key != "ignored"),
            "ignoredRecords": len(splits["ignored"]),
            "gatedSilverRecords": gated_silver,
        },
        "counts": {
            "sourceDomain": dict(sorted(source_domain_counts.items())),
            "eventFamily": dict(sorted(class_counts.items())),
            "split": {key: len(rows) for key, rows in splits.items() if key != "ignored"},
        },
        "loraExport": {
            "summary": {
                "totalRecords": len(lora_rows),
                "trainingEligibleRecords": len(lora_rows),
            },
            "recordsPath": str(output_dir / "videomae_lora_v1" / "records.jsonl"),
            "manifestPath": str(output_dir / "videomae_lora_v1" / "manifest.json"),
        },
        "featureNamesPath": str(output_dir / "feature_names.json"),
    }
    _write_json(output_dir / "manifest.json", manifest)
    _write_json(output_dir / "videomae_lora_v1" / "manifest.json", manifest["loraExport"])
    return manifest


def _vectorize(record: dict[str, Any], feature_names: list[str]) -> list[float]:
    features = record["features"]
    return [float(features.get(name, 0.0)) for name in feature_names]


def _centroid_classifier(records: list[dict[str, Any]], feature_names: list[str], target_key: str) -> dict[str, list[float]]:
    centroids: dict[str, list[list[float]]] = defaultdict(list)
    for record in records:
        label = record.get(target_key)
        if label in (None, "", "unknown"):
            continue
        centroids[str(label)].append(_vectorize(record, feature_names))
    return {
        label: [sum(values) / len(values) for values in zip(*vectors)]
        for label, vectors in centroids.items()
        if vectors
    }


def _predict(centroids: dict[str, list[float]], vector: list[float]) -> str:
    best_label = ""
    best_distance = float("inf")
    for label, centroid in centroids.items():
        distance = sum((a - b) ** 2 for a, b in zip(vector, centroid))
        if distance < best_distance:
            best_distance = distance
            best_label = label
    return best_label


def _confusion_matrix(labels: list[str], predicted: list[str]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for actual, guess in zip(labels, predicted):
        matrix[actual][guess] += 1
    return {actual: dict(sorted(row.items())) for actual, row in sorted(matrix.items())}


def _evaluate(records: list[dict[str, Any]], feature_names: list[str], target_key: str) -> dict[str, Any]:
    train = [record for record in records if record["split"] == "train"]
    eval_rows = [record for record in records if record["split"] in {"val", "test"} and record.get(target_key) not in (None, "", "unknown")]
    if not train or not eval_rows:
        return {"accuracy": 0.0, "count": 0, "confusion": {}}
    centroids = _centroid_classifier(train, feature_names, target_key)
    actual: list[str] = []
    predicted: list[str] = []
    for record in eval_rows:
        actual_label = str(record[target_key])
        guess = _predict(centroids, _vectorize(record, feature_names))
        actual.append(actual_label)
        predicted.append(guess)
    accuracy = sum(1 for a, b in zip(actual, predicted) if a == b) / max(len(actual), 1)
    return {"accuracy": accuracy, "count": len(actual), "confusion": _confusion_matrix(actual, predicted)}


def run_offline_probe(repo_root: Path, bundle_dir: Path) -> dict[str, Any]:
    feature_names = json.loads((bundle_dir / "feature_names.json").read_text())
    records: list[dict[str, Any]] = []
    for split_name in ("train", "val", "test"):
        records.extend(_read_jsonl(bundle_dir / split_name / "records.jsonl"))

    source_split = Counter(record["sourceDomain"] for record in records)
    uncertainty_rate = sum(1 for record in records if float(record["teacherConfidence"]) < 0.8 or float(record["features"].get("runtimeConfidence", 0.0)) < 0.55) / max(len(records), 1)
    report = {
        "schemaVersion": ANNOTATION_SCHEMA_VERSION,
        "bundleDir": str(bundle_dir),
        "sourceDomainSplit": dict(sorted(source_split.items())),
        "uncertaintyRate": uncertainty_rate,
        "eventFamily": _evaluate(records, feature_names, "eventFamily"),
        "outcome": _evaluate(records, feature_names, "outcome"),
        "shotSubtype": _evaluate(records, feature_names, "shotSubtype"),
        "disagreementExamples": [
            {
                "clipId": record["clipId"],
                "sourceDomain": record["sourceDomain"],
                "runtimeLabel": (record.get("rawRuntimeOutputs") or {}).get("label"),
                "teacherLabel": (record.get("rawTeacherOutputs") or {}).get("label"),
                "reviewerNotes": record["reviewerNotes"],
            }
            for record in records
            if record.get("sourceKind") == "silver" and (record.get("rawRuntimeOutputs") or {}).get("label") != (record.get("rawTeacherOutputs") or {}).get("label")
        ][:5],
    }
    _write_json(bundle_dir / "offline_probe_report.json", report)
    return report
