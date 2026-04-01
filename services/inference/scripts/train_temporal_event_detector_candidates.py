from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.app.runtime_models.temporal_student import get_temporal_student_bundle
from services.inference.training.temporal_event_detector import (
    build_temporal_event_detector_report,
    candidate_score,
    evaluate_temporal_event_detector_bundle,
    load_temporal_event_detector_examples,
    train_temporal_event_detector_from_repo,
)
from services.inference.training.temporal_student import evaluate_temporal_student_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and compare temporal detector candidates for phase4c."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "services" / "inference" / "evals" / "temporal_event_detector_candidates",
    )
    parser.add_argument(
        "--write-models",
        action="store_true",
        help="Write the winning bundle into services/inference/models/temporal_event_detector_v1.json.",
    )
    parser.add_argument("--hidden-size", type=int, default=18)
    parser.add_argument("--epochs", type=int, default=140)
    parser.add_argument("--learning-rate", type=float, default=0.02)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    examples = load_temporal_event_detector_examples(REPO_ROOT)
    baseline_bundle = get_temporal_student_bundle(
        str(REPO_ROOT / "services" / "inference" / "models" / "temporal_student_v1.json")
    )
    baseline_metrics = evaluate_temporal_student_bundle(baseline_bundle, examples) if baseline_bundle else {}

    actionformer_path = args.output_dir / "temporal_event_detector_actionformer_v1.json"
    actionformer_result = train_temporal_event_detector_from_repo(
        REPO_ROOT,
        architecture="actionformer",
        output_path=actionformer_path,
        hidden_size=args.hidden_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
    )
    actionformer_metrics = evaluate_temporal_event_detector_bundle(actionformer_result.bundle, examples)

    tridet_path = args.output_dir / "temporal_event_detector_tridet_v1.json"
    tridet_result = train_temporal_event_detector_from_repo(
        REPO_ROOT,
        architecture="tridet",
        output_path=tridet_path,
        hidden_size=args.hidden_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
    )
    tridet_metrics = evaluate_temporal_event_detector_bundle(tridet_result.bundle, examples)

    winner_name = max(
        ("actionformer", "tridet"),
        key=lambda candidate: candidate_score(
            actionformer_metrics if candidate == "actionformer" else tridet_metrics
        ),
    )
    winner_path = actionformer_path if winner_name == "actionformer" else tridet_path
    summary = {
        "baselineMetrics": baseline_metrics,
        "candidates": {
            "actionformer": actionformer_metrics,
            "tridet": tridet_metrics,
        },
        "winner": winner_name,
        "winnerScore": round(
            candidate_score(actionformer_metrics if winner_name == "actionformer" else tridet_metrics),
            4,
        ),
        "winnerBundlePath": str(winner_path),
    }

    if args.write_models:
        model_dir = REPO_ROOT / "services" / "inference" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        final_path = model_dir / "temporal_event_detector_v1.json"
        final_path.write_text(winner_path.read_text(encoding="utf-8"), encoding="utf-8")

    report_path = args.output_dir / "comparison_report.md"
    json_path = args.output_dir / "comparison_report.json"
    report_path.write_text(
        build_temporal_event_detector_report(
            baseline_metrics=baseline_metrics,
            actionformer_metrics=actionformer_metrics,
            tridet_metrics=tridet_metrics,
            winner=winner_name,
        ),
        encoding="utf-8",
    )
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print(report_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
