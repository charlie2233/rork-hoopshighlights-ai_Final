from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, top_k_accuracy_score


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.app.runtime_model import (  # noqa: E402
    EVENT_FAMILIES,
    OUTCOMES,
    RUNTIME_FUSION_SCHEMA_VERSION,
    SHOT_SUBTYPES,
)


DEFAULT_DATASET_DIR = REPO_ROOT / "services" / "inference" / "datasets" / "runtime_training"
DEFAULT_OUTPUT = REPO_ROOT / "services" / "inference" / "models" / "runtime_fusion_v1.json"
DEFAULT_REPORT = REPO_ROOT / "services" / "inference" / "evals" / "runtime_fusion_v1_report.md"
FEATURE_SCHEMA_VERSION = "runtime-fusion-v1"

TARGETS = {
    "eventFamily": EVENT_FAMILIES,
    "outcome": OUTCOMES,
    "shotSubtype": SHOT_SUBTYPES,
}


@dataclass(frozen=True)
class SplitMatrix:
    feature_names: list[str]
    rows: list[dict[str, Any]]
    matrix: np.ndarray


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_dir = args.dataset_dir.resolve()
    train_split = load_split_matrix(args.dataset_dir / "train" / "features.json")
    val_split = load_split_matrix(args.dataset_dir / "val" / "features.json")
    test_split = load_split_matrix(args.dataset_dir / "test" / "features.json")

    feature_names = train_split.feature_names
    if feature_names != val_split.feature_names or feature_names != test_split.feature_names:
        raise RuntimeError("Runtime training feature names differ across splits.")

    promoted_clip_ids: set[str] = set()
    train_rows = list(train_split.rows)
    train_matrix = train_split.matrix
    val_rows = list(val_split.rows)
    val_matrix = val_split.matrix

    for target_name, classes in TARGETS.items():
        promoted = promote_missing_classes(
            target_name=target_name,
            classes=classes,
            train_rows=train_rows,
            train_matrix=train_matrix,
            val_rows=val_rows,
            val_matrix=val_matrix,
        )
        if promoted is None:
            continue
        train_rows, train_matrix, val_rows, val_matrix, clip_ids = promoted
        promoted_clip_ids.update(clip_ids)

    bundle: dict[str, Any] = {
        "schemaVersion": RUNTIME_FUSION_SCHEMA_VERSION,
        "featureSchemaVersion": FEATURE_SCHEMA_VERSION,
        "modelVersion": "runtime-fusion-v1",
        "trainedAt": datetime.now(timezone.utc).isoformat(),
        "sourceDataset": _display_path(dataset_dir),
        "notes": [
            "Teacher outputs remain offline/training-only and are not consumed at runtime.",
            "The runtime head fuses structured signals plus VideoMAE/X-CLIP-derived runtime outputs.",
            "Minimal gold support rows may be promoted from val into train to cover otherwise missing classes; remaining gold rows stay held out.",
        ],
        "featureNames": feature_names,
        "targets": {},
        "supportPromotion": sorted(promoted_clip_ids),
    }
    report: dict[str, Any] = {
        "summary": {
            "datasetDir": _display_path(dataset_dir),
            "featureCount": len(feature_names),
            "trainRows": len(train_rows),
            "valRows": len(val_rows),
            "testRows": len(test_split.rows),
            "promotedClipIds": sorted(promoted_clip_ids),
        },
        "targets": {},
    }

    for target_name, classes in TARGETS.items():
        trained = train_target(
            target_name=target_name,
            classes=classes,
            train_rows=train_rows,
            train_matrix=train_matrix,
            val_rows=val_rows,
            val_matrix=val_matrix,
            test_rows=test_split.rows,
            test_matrix=test_split.matrix,
        )
        bundle["targets"][target_name] = trained["bundle"]
        report["targets"][target_name] = trained["report"]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(render_report(report), encoding="utf-8")
    print(args.output)
    print(args.report_output)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and export the runtime fusion basketball labeler.")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(argv)


def load_split_matrix(path: Path) -> SplitMatrix:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SplitMatrix(
        feature_names=[str(item) for item in payload.get("featureNames", [])],
        rows=list(payload.get("rows", [])),
        matrix=np.asarray(payload.get("matrix", []), dtype=np.float64),
    )


def promote_missing_classes(
    *,
    target_name: str,
    classes: tuple[str, ...],
    train_rows: list[dict[str, Any]],
    train_matrix: np.ndarray,
    val_rows: list[dict[str, Any]],
    val_matrix: np.ndarray,
) -> tuple[list[dict[str, Any]], np.ndarray, list[dict[str, Any]], np.ndarray, set[str]] | None:
    present = {normalize_target_value(target_name, row) for row in train_rows}
    missing = [label for label in classes if label not in present]
    if not missing:
        return None

    promoted_indices: list[int] = []
    promoted_clip_ids: set[str] = set()
    for label in missing:
        for index, row in enumerate(val_rows):
            if index in promoted_indices:
                continue
            if normalize_target_value(target_name, row) != label:
                continue
            promoted_indices.append(index)
            promoted_clip_ids.add(str(row["clipId"]))
            break

    if not promoted_indices:
        return None

    promoted_rows = [val_rows[index] for index in promoted_indices]
    promoted_matrix = val_matrix[promoted_indices]
    remaining_rows = [row for index, row in enumerate(val_rows) if index not in promoted_indices]
    remaining_matrix = np.asarray([row for index, row in enumerate(val_matrix.tolist()) if index not in promoted_indices], dtype=np.float64)
    return (
        train_rows + promoted_rows,
        np.vstack([train_matrix, promoted_matrix]) if train_matrix.size else promoted_matrix,
        remaining_rows,
        remaining_matrix,
        promoted_clip_ids,
    )


def train_target(
    *,
    target_name: str,
    classes: tuple[str, ...],
    train_rows: list[dict[str, Any]],
    train_matrix: np.ndarray,
    val_rows: list[dict[str, Any]],
    val_matrix: np.ndarray,
    test_rows: list[dict[str, Any]],
    test_matrix: np.ndarray,
) -> dict[str, Any]:
    y_train = np.asarray([normalize_target_value(target_name, row) for row in train_rows], dtype=object)
    y_val = np.asarray([normalize_target_value(target_name, row) for row in val_rows], dtype=object)
    y_test = np.asarray([normalize_target_value(target_name, row) for row in test_rows], dtype=object)
    w_train = np.asarray([float(row.get("weight", 1.0)) for row in train_rows], dtype=np.float64)

    classifier = LogisticRegression(
        max_iter=4000,
        solver="lbfgs",
        class_weight="balanced",
        random_state=42,
    )
    classifier.fit(train_matrix, y_train, sample_weight=w_train)

    val_logits = classifier.decision_function(val_matrix)
    val_logits = ensure_2d_logits(val_logits, classifier.classes_)
    temperature = fit_temperature(val_logits, y_val, classifier.classes_)
    val_probabilities = softmax_with_temperature(val_logits, temperature)
    uncertainty_threshold, margin_threshold = derive_thresholds(val_probabilities, y_val, classifier.classes_)

    test_logits = classifier.decision_function(test_matrix)
    test_logits = ensure_2d_logits(test_logits, classifier.classes_)
    test_probabilities = softmax_with_temperature(test_logits, temperature)

    report = {
        "classes": list(classifier.classes_),
        "trainSupport": dict(Counter(str(label) for label in y_train)),
        "valSupport": dict(Counter(str(label) for label in y_val)),
        "testSupport": dict(Counter(str(label) for label in y_test)),
        "temperature": round(temperature, 4),
        "uncertaintyThreshold": round(uncertainty_threshold, 4),
        "marginThreshold": round(margin_threshold, 4),
        "validation": evaluate_probabilities(y_val, val_probabilities, classifier.classes_),
        "test": evaluate_probabilities(y_test, test_probabilities, classifier.classes_),
    }
    bundle = {
        "classes": [str(item) for item in classifier.classes_],
        "intercept": np.asarray(classifier.intercept_, dtype=np.float64).tolist(),
        "coefficients": np.asarray(classifier.coef_, dtype=np.float64).tolist(),
        "temperature": round(temperature, 4),
        "uncertaintyThreshold": round(uncertainty_threshold, 4),
        "marginThreshold": round(margin_threshold, 4),
        "topK": 3,
    }
    return {"bundle": bundle, "report": report}


def normalize_target_value(target_name: str, row: dict[str, Any]) -> str:
    value = row.get(target_name)
    if target_name == "shotSubtype":
        if value in {None, "None", "unknown"}:
            return "null"
    if value is None:
        return "other" if target_name == "eventFamily" else "uncertain"
    return str(value)


def ensure_2d_logits(logits: np.ndarray, classes: np.ndarray) -> np.ndarray:
    if logits.ndim == 1:
        logits = np.stack([-logits, logits], axis=1)
    if logits.shape[1] != len(classes):
        raise RuntimeError("Classifier logits do not match class count.")
    return logits


def fit_temperature(logits: np.ndarray, labels: np.ndarray, classes: np.ndarray) -> float:
    if logits.size == 0 or labels.size == 0:
        return 1.0
    label_to_index = {str(label): index for index, label in enumerate(classes)}
    label_indices = np.asarray([label_to_index[str(label)] for label in labels], dtype=np.int64)
    best_temperature = 1.0
    best_loss = float("inf")
    for temperature in np.linspace(0.6, 2.4, 37):
        probabilities = softmax_with_temperature(logits, float(temperature))
        loss = negative_log_likelihood(probabilities, label_indices)
        if loss < best_loss:
            best_loss = loss
            best_temperature = float(temperature)
    return best_temperature


def derive_thresholds(probabilities: np.ndarray, labels: np.ndarray, classes: np.ndarray) -> tuple[float, float]:
    if probabilities.size == 0 or labels.size == 0:
        return (0.45, 0.05)
    class_lookup = {str(label): index for index, label in enumerate(classes)}
    top_indices = np.argmax(probabilities, axis=1)
    top_scores = probabilities[np.arange(len(probabilities)), top_indices]
    sorted_scores = np.sort(probabilities, axis=1)
    margins = sorted_scores[:, -1] - sorted_scores[:, -2] if probabilities.shape[1] > 1 else np.ones(len(probabilities))
    correct_mask = np.asarray([top_index == class_lookup[str(label)] for top_index, label in zip(top_indices, labels)], dtype=bool)
    if not np.any(correct_mask):
        return (0.45, 0.05)
    uncertainty_threshold = float(np.clip(np.quantile(top_scores[correct_mask], 0.15), 0.42, 0.75))
    margin_threshold = float(np.clip(np.quantile(margins[correct_mask], 0.15), 0.04, 0.2))
    return (uncertainty_threshold, margin_threshold)


def softmax_with_temperature(logits: np.ndarray, temperature: float) -> np.ndarray:
    scaled = logits / max(temperature, 1e-3)
    shifted = scaled - np.max(scaled, axis=1, keepdims=True)
    exponentials = np.exp(shifted)
    totals = np.sum(exponentials, axis=1, keepdims=True)
    return exponentials / np.maximum(totals, 1e-9)


def negative_log_likelihood(probabilities: np.ndarray, label_indices: np.ndarray) -> float:
    chosen = probabilities[np.arange(len(probabilities)), label_indices]
    return float(-np.mean(np.log(np.clip(chosen, 1e-9, 1.0))))


def evaluate_probabilities(labels: np.ndarray, probabilities: np.ndarray, classes: np.ndarray) -> dict[str, Any]:
    if labels.size == 0:
        return {"sampleCount": 0}
    class_lookup = {str(label): index for index, label in enumerate(classes)}
    predicted_indices = np.argmax(probabilities, axis=1)
    predictions = np.asarray([str(classes[index]) for index in predicted_indices], dtype=object)
    accuracy = accuracy_score(labels, predictions)
    macro_f1 = f1_score(labels, predictions, average="macro")
    top_k = 2 if probabilities.shape[1] > 1 else 1
    top_k_accuracy = top_k_accuracy_score(labels, probabilities, labels=list(classes), k=top_k)
    matrix = confusion_matrix(labels, predictions, labels=list(classes))
    confusion_rows = []
    for row_index, expected in enumerate(classes):
        for col_index, predicted in enumerate(classes):
            count = int(matrix[row_index, col_index])
            if count:
                confusion_rows.append({"expected": str(expected), "predicted": str(predicted), "count": count})
    return {
        "sampleCount": int(labels.size),
        "accuracy": round(float(accuracy), 4),
        "macroF1": round(float(macro_f1), 4),
        "top2Accuracy": round(float(top_k_accuracy), 4),
        "labelDistribution": dict(Counter(str(label) for label in labels)),
        "predictionDistribution": dict(Counter(str(label) for label in predictions)),
        "confusions": confusion_rows,
    }


def render_report(report: dict[str, Any]) -> str:
    lines = ["# Runtime Fusion Model Report", ""]
    summary = report["summary"]
    lines.append(f"- Feature count: `{summary['featureCount']}`")
    lines.append(f"- Train rows: `{summary['trainRows']}`")
    lines.append(f"- Validation rows: `{summary['valRows']}`")
    lines.append(f"- Test rows: `{summary['testRows']}`")
    lines.append(f"- Support-promoted gold clips: `{len(summary['promotedClipIds'])}`")
    if summary["promotedClipIds"]:
        lines.append(f"- Promoted clip IDs: `{', '.join(summary['promotedClipIds'])}`")
    lines.append("")
    for target_name, target_report in report["targets"].items():
        lines.append(f"## {target_name}")
        lines.append(f"- Temperature: `{target_report['temperature']}`")
        lines.append(f"- Uncertainty threshold: `{target_report['uncertaintyThreshold']}`")
        lines.append(f"- Margin threshold: `{target_report['marginThreshold']}`")
        lines.append(f"- Train support: `{target_report['trainSupport']}`")
        lines.append(f"- Validation accuracy/macroF1: `{target_report['validation']['accuracy']}` / `{target_report['validation']['macroF1']}`")
        lines.append(f"- Test accuracy/macroF1: `{target_report['test']['accuracy']}` / `{target_report['test']['macroF1']}`")
        lines.append(f"- Test top-2 accuracy: `{target_report['test']['top2Accuracy']}`")
        lines.append("")
    return "\n".join(lines)


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
