from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, top_k_accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TARGETS = {
    "eventFamily": ["shot_attempt", "turnover", "defensive_event", "transition", "other"],
    "outcome": ["made", "missed", "blocked", "uncertain"],
    "shotSubtype": ["dunk", "layup", "jumper", "three", "putback", "unknown"],
}


@dataclass
class ProbeDataset:
    rows: list[dict[str, Any]]

    def by_clip_id(self) -> dict[str, dict[str, Any]]:
        return {str(row["clipId"]): row for row in self.rows}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gold = load_jsonl(args.gold_dataset)
    silver = load_jsonl(args.silver_dataset) if args.silver_dataset else ProbeDataset([])
    report = build_probe_report(gold, silver)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "offline_probe_report.json"
    md_path = args.output_dir / "offline_probe_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(md_path)
    print(json_path)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train an interpretable probe over basketball annotations.")
    repo_root = Path(__file__).resolve().parents[3]
    default_dataset_dir = repo_root / "services" / "inference" / "datasets"
    parser.add_argument("--gold-dataset", type=Path, default=default_dataset_dir / "gold_annotations.jsonl")
    parser.add_argument("--silver-dataset", type=Path, default=default_dataset_dir / "silver_teacher_annotations.jsonl")
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/hoopsclips-offline-probe"))
    return parser.parse_args(argv)


def load_jsonl(path: Path) -> ProbeDataset:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return ProbeDataset(rows)


def build_probe_report(gold: ProbeDataset, silver: ProbeDataset) -> dict[str, Any]:
    gold_rows = gold.rows
    silver_rows = silver.by_clip_id()
    runtime_teacher_overlap = [build_runtime_teacher_disagreement(row, silver_rows.get(row["clipId"])) for row in gold_rows if silver_rows.get(row["clipId"]) is not None]

    report: dict[str, Any] = {
        "summary": {
            "goldClips": len(gold_rows),
            "silverClips": len(silver.rows),
            "sourceDomainSplit": dict(Counter(row["sourceDomain"] for row in gold_rows)),
            "humanVerifiedCount": sum(1 for row in gold_rows if row.get("humanVerified")),
            "teacherPseudoCount": sum(1 for row in silver.rows if not row.get("humanVerified")),
        },
        "labelDistribution": distribution(gold_rows, "eventFamily"),
        "outcomeDistribution": distribution(gold_rows, "outcome"),
        "shotSubtypeDistribution": distribution(gold_rows, "shotSubtype"),
        "disagreementDistribution": disagreement_distribution(runtime_teacher_overlap),
        "missVsMadeConfusion": miss_vs_made_confusion(runtime_teacher_overlap),
        "uncertaintyRate": uncertainty_rate(gold_rows),
        "sourceDomainBreakdown": source_domain_breakdown(gold_rows),
        "correctedLabelExamples": corrected_label_examples(runtime_teacher_overlap),
        "separability": {},
    }

    for target in TARGETS:
        report["separability"][target] = probe_target(gold_rows, target)

    report["featureImportances"] = {
        target: report["separability"][target]["runtimePlusTeacher"]["topFeatures"]
        for target in TARGETS
    }
    return report


def probe_target(rows: list[dict[str, Any]], target: str) -> dict[str, Any]:
    labels = [normalize_target(row[target]) for row in rows]
    feature_sets = {
        "runtimeOnly": [build_features(row, include_teacher=False) for row in rows],
        "runtimePlusTeacher": [build_features(row, include_teacher=True) for row in rows],
    }
    result: dict[str, Any] = {}
    for variant_name, feature_rows in feature_sets.items():
        result[variant_name] = evaluate_model(feature_rows, labels, target)
    return result


def evaluate_model(feature_rows: list[dict[str, Any]], labels: list[str], target: str) -> dict[str, Any]:
    label_counts = Counter(labels)
    min_class_count = min(label_counts.values())
    n_splits = max(2, min(5, min_class_count))
    model = make_pipeline(
        DictVectorizer(sparse=True),
        LogisticRegression(
            max_iter=2000,
            solver="lbfgs",
            multi_class="multinomial",
            class_weight="balanced",
        ),
    )
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    fitted = model.fit(feature_rows, labels)
    class_order = list(fitted.named_steps["logisticregression"].classes_)
    proba = cross_val_predict(model, feature_rows, labels, cv=cv, method="predict_proba")
    predictions = [class_order[int(index)] for index in np.argmax(proba, axis=1)]
    top2_hit = sum(
        1
        for actual, row in zip(labels, proba)
        if actual in [class_order[idx] for idx in np.argsort(row)[-2:]]
    )
    accuracy = accuracy_score(labels, predictions)
    macro_f1 = f1_score(labels, predictions, average="macro")
    top2_accuracy = top2_hit / max(len(labels), 1)

    vectorizer = fitted.named_steps["dictvectorizer"]
    clf = fitted.named_steps["logisticregression"]
    top_features = []
    feature_names = vectorizer.get_feature_names_out()
    if len(clf.classes_) > 1:
        target_index = int(np.argmax([cls == clf.classes_[0] for cls in clf.classes_]))
        class_name = clf.classes_[target_index]
        class_index = list(clf.classes_).index(class_name)
        coefs = clf.coef_[class_index]
        feature_pairs = sorted(zip(feature_names, coefs), key=lambda item: item[1], reverse=True)
        top_features = [{"feature": name, "weight": round(float(weight), 4)} for name, weight in feature_pairs[:10]]

    matrix = confusion_matrix(labels, predictions, labels=list(TARGETS[target]))
    confusion_rows = []
    for actual_index, actual in enumerate(TARGETS[target]):
        for predicted_index, predicted in enumerate(TARGETS[target]):
            count = int(matrix[actual_index, predicted_index])
            if count:
                confusion_rows.append({"expected": actual, "predicted": predicted, "count": count})

    return {
        "summary": {
            "accuracy": round(float(accuracy), 4),
            "macroF1": round(float(macro_f1), 4),
            "top2Accuracy": round(float(top2_accuracy), 4),
            "folds": n_splits,
        },
        "perClass": class_support(labels, predictions),
        "confusions": confusion_rows,
        "topFeatures": top_features,
    }


def build_features(row: dict[str, Any], *, include_teacher: bool) -> dict[str, Any]:
    runtime = row["rawRuntimeOutputs"]
    teacher = row["rawTeacherOutputs"]
    features: dict[str, Any] = {
        "ballVisible": int(bool(row["ballVisible"])),
        "hoopVisible": int(bool(row["hoopVisible"])),
        "ballNearRim": float(row["ballNearRim"]),
        "ballThroughHoopLikelihood": float(row["ballThroughHoopLikelihood"]),
        "possessionChangeLikelihood": float(row["possessionChangeLikelihood"]),
        "transitionLikelihood": float(row["transitionLikelihood"]),
        "teacherConfidence": float(row["teacherConfidence"]),
        "humanVerified": int(bool(row["humanVerified"])),
        f"sourceDomain={row['sourceDomain']}": 1,
        f"runtimeLabel={runtime.get('label')}": 1,
        f"runtimeEventFamily={runtime.get('eventFamily')}": 1,
        f"runtimeOutcome={runtime.get('outcome')}": 1,
        f"runtimeShotSubtype={runtime.get('shotSubtype') or 'null'}": 1,
        f"runtimeTop1={first_label(runtime.get('topKLabels', []))}": 1,
        f"runtimeVideoMAE={first_label(runtime.get('videoMAE', {}).get('topK', []), label_key='label')}": 1,
        f"runtimeXCLIP={first_label(runtime.get('xclip', {}).get('topK', []), label_key='label')}": 1,
    }
    for key, value in (runtime.get("structuredSignals") or {}).items():
        features[f"runtimeSignal={key}"] = float(value) if value is not None else 0.0
    if include_teacher:
        features.update(
            {
                f"teacherEventFamily={teacher.get('eventFamily')}": 1,
                f"teacherOutcome={teacher.get('outcome')}": 1,
                f"teacherShotSubtype={teacher.get('shotSubtype') or 'null'}": 1,
                f"teacherDisplay={teacher.get('displayLabelSuggestion')}": 1,
                f"teacherSourceDomain={teacher.get('sourceDomain')}": 1,
                "teacherConfidenceFeature": float(teacher.get("confidence", 0.0)),
            }
        )
    return features


def first_label(items: list[Any], *, label_key: str = "label") -> str:
    if not items:
        return "none"
    item = items[0]
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get(label_key) or item.get("canonicalLabel") or item.get("rawLabel") or "none")
    return "none"


def build_runtime_teacher_disagreement(gold_row: dict[str, Any], silver_row: dict[str, Any] | None) -> dict[str, Any]:
    if silver_row is None:
        return {}
    runtime = gold_row["rawRuntimeOutputs"]
    teacher = silver_row["rawTeacherOutputs"]
    reasons = []
    if runtime.get("label") == "Highlight":
        reasons.append("app_facing_highlight_only")
    if normalize_target(runtime.get("outcome")) != normalize_target(teacher.get("outcome")):
        reasons.append("runtime_teacher_outcome_disagreement")
    if normalize_target(runtime.get("eventFamily")) != normalize_target(teacher.get("eventFamily")):
        reasons.append("runtime_teacher_family_disagreement")
    if normalize_target(runtime.get("shotSubtype")) != normalize_target(teacher.get("shotSubtype")):
        reasons.append("runtime_teacher_subtype_disagreement")
    if runtime.get("outcome") == "made" and gold_row["outcome"] == "missed":
        reasons.append("miss_vs_made_disagreement")
    if gold_row["shotSubtype"] is None and gold_row["ballNearRim"] > 0.7:
        reasons.append("strong_ball_hoop_without_subtype")
    if float(teacher.get("confidence", 0.0)) >= 0.8 and float(runtime.get("confidence", 0.0)) <= 0.65:
        reasons.append("high_teacher_low_runtime")
    return {
        "clipId": gold_row["clipId"],
        "sourceDomain": gold_row["sourceDomain"],
        "gold": {
            "eventFamily": gold_row["eventFamily"],
            "outcome": gold_row["outcome"],
            "shotSubtype": gold_row["shotSubtype"],
        },
        "runtime": {
            "eventFamily": runtime.get("eventFamily"),
            "outcome": runtime.get("outcome"),
            "shotSubtype": runtime.get("shotSubtype"),
            "label": runtime.get("label"),
            "confidence": runtime.get("confidence"),
        },
        "teacher": {
            "eventFamily": teacher.get("eventFamily"),
            "outcome": teacher.get("outcome"),
            "shotSubtype": teacher.get("shotSubtype"),
            "confidence": teacher.get("confidence"),
        },
        "reasons": unique_ordered(reasons),
    }


def disagreement_distribution(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter()
    for item in items:
        for reason in item.get("reasons", []):
            counts[reason] += 1
    return dict(counts)


def miss_vs_made_confusion(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for item in items:
        if "miss_vs_made_disagreement" in item.get("reasons", []):
            counts["miss_to_made"] += 1
        if item.get("gold", {}).get("outcome") == "missed" and item.get("teacher", {}).get("outcome") == "made":
            counts["gold_miss_teacher_made"] += 1
    return dict(counts)


def uncertainty_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    uncertain = sum(1 for row in rows if row.get("outcome") == "uncertain" or row["rawRuntimeOutputs"].get("label") == "Highlight")
    return round(uncertain / len(rows), 4)


def source_domain_breakdown(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(row["sourceDomain"] for row in rows))


def corrected_label_examples(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    examples = []
    for item in items:
        gold = item.get("gold", {})
        runtime = item.get("runtime", {})
        teacher = item.get("teacher", {})
        if gold.get("outcome") != teacher.get("outcome") or gold.get("eventFamily") != teacher.get("eventFamily"):
            examples.append(
                {
                    "clipId": item["clipId"],
                    "gold": gold,
                    "runtime": runtime,
                    "teacher": teacher,
                }
            )
    return examples[:8]


def distribution(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(normalize_target(row[field]) for row in rows))


def class_support(labels: list[str], predictions: list[str]) -> list[dict[str, Any]]:
    counts = Counter(labels)
    support = []
    for label in sorted(counts):
        support.append(
            {
                "label": label,
                "support": counts[label],
                "correct": sum(1 for actual, predicted in zip(labels, predictions) if actual == label and predicted == label),
            }
        )
    return support


def normalize_target(value: Any) -> str:
    if value is None:
        return "null"
    text = str(value).strip().lower()
    if text in {"shot", "shot_attempt"}:
        return "shot_attempt"
    if text in {"fastbreak", "fast break"}:
        return "transition"
    if text in {"make", "made"}:
        return "made"
    if text in {"miss", "missed"}:
        return "missed"
    if text in {"block", "blocked"}:
        return "blocked"
    return text


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Offline Probe Report", ""]
    summary = report["summary"]
    lines.append(f"- Gold clips: `{summary['goldClips']}`")
    lines.append(f"- Silver clips: `{summary['silverClips']}`")
    lines.append(f"- Human verified: `{summary['humanVerifiedCount']}`")
    lines.append(f"- Teacher pseudo-labels: `{summary['teacherPseudoCount']}`")
    lines.append("")
    lines.append("## Separability")
    for target, variants in report["separability"].items():
        lines.append(f"### {target}")
        for variant, metrics in variants.items():
            lines.append(
                f"- `{variant}` accuracy `{metrics['summary']['accuracy']}` macroF1 `{metrics['summary']['macroF1']}` top2 `{metrics['summary']['top2Accuracy']}`"
            )
    lines.append("")
    lines.append("## Disagreements")
    for reason, count in report["disagreementDistribution"].items():
        lines.append(f"- `{reason}`: `{count}`")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
