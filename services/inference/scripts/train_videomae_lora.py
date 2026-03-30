from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.training.videomae_lora import train_and_export_lora_run


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = train_and_export_lora_run(
        repo_root=REPO_ROOT,
        output_dir=args.output_dir,
        model_name=args.model_name,
        tiny_smoke=args.tiny_smoke,
        frame_count=args.frame_count,
        image_size=args.image_size,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        device=args.device,
        r=args.r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
    )
    summary_path = args.output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(_summarize_result(result), indent=2, sort_keys=True), encoding="utf-8")
    print(summary_path)
    print(args.output_dir / "comparison_report.md")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train frozen baseline vs rsLoRA VideoMAE adapters.")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "evals" / "videomae_lora")
    parser.add_argument("--model-name", type=str, default="MCG-NJU/videomae-base-finetuned-kinetics")
    parser.add_argument("--tiny-smoke", action="store_true")
    parser.add_argument("--frame-count", type=int, default=8)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    return parser.parse_args(argv)


def _summarize_result(result) -> dict[str, object]:
    return {
        "schemaVersion": result.schema_version,
        "featureSchemaVersion": result.feature_schema_version,
        "modelVersion": result.model_version,
        "sourceDataset": result.source_dataset,
        "trainedAt": result.trained_at,
        "tinySmoke": result.tiny_smoke,
        "manifest": result.manifest,
        "baselineMetrics": result.baseline_metrics,
        "rsloraMetrics": result.rslora_metrics,
        "artifacts": [artifact.path.name for artifact in result.artifacts],
    }


if __name__ == "__main__":
    raise SystemExit(main())
