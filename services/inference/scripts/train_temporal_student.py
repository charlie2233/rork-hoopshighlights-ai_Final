from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.training.temporal_student import (
    build_temporal_student_report,
    evaluate_temporal_student_bundle,
    load_temporal_student_examples,
    train_temporal_student_from_repo,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and evaluate the basketball temporal student.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "services" / "inference" / "evals" / "temporal_student_v1",
    )
    parser.add_argument(
        "--write-models",
        action="store_true",
        help="Write the trained student bundle into services/inference/models/.",
    )
    parser.add_argument("--hidden-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = args.output_dir / "temporal_student_v1.json"
    result = train_temporal_student_from_repo(
        REPO_ROOT,
        output_path=bundle_path,
        hidden_size=args.hidden_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
    )
    examples = load_temporal_student_examples(REPO_ROOT)
    metrics = evaluate_temporal_student_bundle(result.bundle, examples)

    if args.write_models:
        model_dir = REPO_ROOT / "services" / "inference" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / "temporal_student_v1.json"
        model_path.write_text(bundle_path.read_text(encoding="utf-8"), encoding="utf-8")

    report_path = args.output_dir / "report.md"
    json_path = args.output_dir / "report.json"
    report_path.write_text(
        build_temporal_student_report(metrics=metrics, evaluation_rows=metrics.get("evaluationRows") or []),
        encoding="utf-8",
    )
    json_path.write_text(json.dumps({"trainingMetrics": result.metrics, "evaluationMetrics": metrics}, indent=2, sort_keys=True), encoding="utf-8")

    print(bundle_path)
    print(report_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
