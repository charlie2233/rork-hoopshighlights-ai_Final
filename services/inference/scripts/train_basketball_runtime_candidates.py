from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.training.teacher_distilled_student import build_teacher_distilled_student_bundle
from services.inference.training.temporal_encoder import (
    evaluate_temporal_encoder_bundle,
    load_temporal_training_examples,
    train_temporal_encoder_from_repo,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and compare basketball-specific runtime encoder candidates."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "services" / "inference" / "evals" / "basketball_runtime_candidates",
    )
    parser.add_argument(
        "--write-models",
        action="store_true",
        help="Write the trained candidate bundles into services/inference/models/ for runtime rollout.",
    )
    parser.add_argument("--temporal-hidden-size", type=int, default=12)
    parser.add_argument("--temporal-epochs", type=int, default=120)
    parser.add_argument("--temporal-learning-rate", type=float, default=0.03)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    temporal_output_path = args.output_dir / "temporal_encoder_v1.json"
    temporal_examples = load_temporal_training_examples(REPO_ROOT)
    temporal_result = train_temporal_encoder_from_repo(
        REPO_ROOT,
        output_path=temporal_output_path,
        hidden_size=args.temporal_hidden_size,
        epochs=args.temporal_epochs,
        learning_rate=args.temporal_learning_rate,
    )
    temporal_metrics = evaluate_temporal_encoder_bundle(temporal_result.bundle, temporal_examples)

    teacher_distilled_output_dir = args.output_dir / "teacher_distilled"
    teacher_distilled_result = build_teacher_distilled_student_bundle(REPO_ROOT, output_dir=teacher_distilled_output_dir)
    teacher_distilled_bundle_path = args.output_dir / "teacher_distilled_clip_student_v1.json"
    teacher_distilled_result.bundle.save(teacher_distilled_bundle_path)

    if args.write_models:
        model_dir = REPO_ROOT / "services" / "inference" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        temporal_model_path = model_dir / "temporal_encoder_v1.json"
        teacher_distilled_model_path = model_dir / "teacher_distilled_clip_student_v1.json"
        temporal_model_path.write_text(temporal_output_path.read_text(encoding="utf-8"), encoding="utf-8")
        teacher_distilled_model_path.write_text(
            teacher_distilled_bundle_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    summary = build_summary(
        baseline_metrics=teacher_distilled_result.baseline_metrics,
        temporal_metrics=temporal_metrics,
        distilled_metrics=teacher_distilled_result.distilled_metrics,
    )
    report_path = args.output_dir / "comparison_report.md"
    json_path = args.output_dir / "comparison_report.json"
    report_path.write_text(render_report(summary), encoding="utf-8")
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print(report_path)
    print(json_path)
    return 0


def build_summary(
    *,
    baseline_metrics: dict[str, object],
    temporal_metrics: dict[str, object],
    distilled_metrics: dict[str, object],
) -> dict[str, object]:
    scoreboard = {
        "phase3e2Baseline": baseline_metrics,
        "temporalStudent": temporal_metrics,
        "teacherDistilledStudent": distilled_metrics,
    }
    winner = max(
        ("temporalStudent", "teacherDistilledStudent"),
        key=lambda key: candidate_score(scoreboard[key]),
    )
    return {
        "scoreboard": scoreboard,
        "winner": winner,
        "winnerScore": round(candidate_score(scoreboard[winner]), 4),
    }


def candidate_score(metrics: dict[str, object]) -> float:
    return (
        float(metrics.get("eventFamilyAccuracy", 0.0))
        + float(metrics.get("outcomeAccuracy", 0.0))
        + (0.5 * float(metrics.get("shotSubtypeAccuracy", 0.0)))
        + (0.1 * float(metrics.get("flatLabelSpread", 0.0)))
        - float(metrics.get("uncertaintyRate", 0.0))
    )


def render_report(summary: dict[str, object]) -> str:
    scoreboard = summary["scoreboard"]
    lines = [
        "# Basketball Runtime Candidate Comparison",
        "",
        f"- Winner: `{summary['winner']}`",
        f"- Winner score: `{summary['winnerScore']}`",
        "",
        "## Candidate Metrics",
    ]
    for name, metrics in scoreboard.items():
        lines.extend(
            [
                f"### {name}",
                f"- eventFamilyAccuracy: `{metrics.get('eventFamilyAccuracy')}`",
                f"- outcomeAccuracy: `{metrics.get('outcomeAccuracy')}`",
                f"- shotSubtypeAccuracy: `{metrics.get('shotSubtypeAccuracy')}`",
                f"- uncertaintyRate: `{metrics.get('uncertaintyRate')}`",
                f"- flatLabelSpread: `{metrics.get('flatLabelSpread')}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
