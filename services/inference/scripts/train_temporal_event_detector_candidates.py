from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.app.runtime_models.temporal_event_detector import (
    load_temporal_event_detector_bundle,
    write_temporal_event_detector_bundle,
)
from services.inference.app.runtime_models.temporal_student import get_temporal_student_bundle
from services.inference.training.temporal_event_detector import (
    build_temporal_event_detector_report,
    candidate_score,
    evaluate_temporal_event_detector_bundle,
    load_temporal_event_detector_examples,
    refresh_shot_specialist_bundle,
    train_temporal_event_detector_from_repo,
)
from services.inference.training.temporal_student import evaluate_temporal_student_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train temporal event detector candidates or refresh the frozen shot-specialist head."
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
    parser.add_argument(
        "--write-model-architecture",
        choices=("winner", "actionformer", "tridet"),
        default="winner",
        help="Select which candidate bundle to write when --write-models is set.",
    )
    parser.add_argument(
        "--freeze-proposal-stack",
        action="store_true",
        help="Keep the current detector / verifier / ranker stack frozen and refresh only the shot-specialist targets.",
    )
    parser.add_argument(
        "--base-bundle-path",
        type=Path,
        default=REPO_ROOT / "services" / "inference" / "models" / "temporal_event_detector_v1.json",
        help="Path to the existing deployed temporal detector bundle when --freeze-proposal-stack is used.",
    )
    parser.add_argument("--hidden-size", type=int, default=18)
    parser.add_argument("--epochs", type=int, default=140)
    parser.add_argument("--learning-rate", type=float, default=0.02)
    return parser.parse_args()


def build_shot_specialist_refresh_report(
    *,
    baseline_metrics: dict[str, object],
    refresh_metrics: dict[str, object],
) -> str:
    return "\n".join(
        [
            "# Frozen Proposal Stack Shot-Specialist Refresh",
            "",
            "## Baseline",
            "",
            f"- Proposal acceptance rate: `{baseline_metrics.get('proposalAcceptanceRate')}`",
            f"- Accepted-shot outcome accuracy: `{baseline_metrics.get('acceptedShotProposalOutcomeAccuracy')}`",
            f"- Accepted-shot subtype distribution: `{baseline_metrics.get('acceptedShotSubtypeDistribution')}`",
            f"- Accepted-shot abstention rate: `{baseline_metrics.get('acceptedShotAbstentionRate')}`",
            f"- Dunk dominance: `{baseline_metrics.get('dunkDominance')}`",
            f"- Uncertainty rate: `{baseline_metrics.get('uncertaintyRate')}`",
            "",
            "## Specialist Refresh",
            "",
            f"- Proposal acceptance rate: `{refresh_metrics.get('proposalAcceptanceRate')}`",
            f"- Accepted-shot outcome accuracy: `{refresh_metrics.get('acceptedShotProposalOutcomeAccuracy')}`",
            f"- Accepted-shot subtype distribution: `{refresh_metrics.get('acceptedShotSubtypeDistribution')}`",
            f"- Accepted-shot abstention rate: `{refresh_metrics.get('acceptedShotAbstentionRate')}`",
            f"- Dunk dominance: `{refresh_metrics.get('dunkDominance')}`",
            f"- Uncertainty rate: `{refresh_metrics.get('uncertaintyRate')}`",
            f"- Flat label distribution: `{refresh_metrics.get('flatLabelDistribution')}`",
            f"- EventFamily distribution: `{refresh_metrics.get('eventFamilyDistribution')}`",
        ]
    )


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    examples = load_temporal_event_detector_examples(REPO_ROOT)
    if args.freeze_proposal_stack:
        base_bundle = load_temporal_event_detector_bundle(args.base_bundle_path)
        baseline_metrics = evaluate_temporal_event_detector_bundle(base_bundle, examples)
        refreshed_bundle = refresh_shot_specialist_bundle(
            base_bundle,
            examples,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
        )
        refresh_path = args.output_dir / "temporal_event_detector_shot_specialist_refresh_v1.json"
        write_temporal_event_detector_bundle(refresh_path, refreshed_bundle)
        refresh_metrics = evaluate_temporal_event_detector_bundle(refreshed_bundle, examples)
        summary = {
            "baselineMetrics": baseline_metrics,
            "shotSpecialistRefreshMetrics": refresh_metrics,
            "winner": "shot-specialist-refresh",
            "winnerScore": round(candidate_score(refresh_metrics), 4),
            "winnerBundlePath": str(refresh_path),
        }
        if args.write_models:
            model_dir = REPO_ROOT / "services" / "inference" / "models"
            model_dir.mkdir(parents=True, exist_ok=True)
            final_path = model_dir / "temporal_event_detector_v1.json"
            final_path.write_text(refresh_path.read_text(encoding="utf-8"), encoding="utf-8")

        report_path = args.output_dir / "comparison_report.md"
        json_path = args.output_dir / "comparison_report.json"
        report_path.write_text(
            build_shot_specialist_refresh_report(
                baseline_metrics=baseline_metrics,
                refresh_metrics=refresh_metrics,
            ),
            encoding="utf-8",
        )
        json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        print(report_path)
        print(json_path)
        return 0

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
        selected_name = winner_name if args.write_model_architecture == "winner" else args.write_model_architecture
        selected_path = actionformer_path if selected_name == "actionformer" else tridet_path
        final_path.write_text(selected_path.read_text(encoding="utf-8"), encoding="utf-8")

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
