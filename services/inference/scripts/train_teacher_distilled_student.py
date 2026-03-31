from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.training.teacher_distilled_student import build_teacher_distilled_student_bundle


DEFAULT_OUTPUT_DIR = REPO_ROOT / "services" / "inference" / "evals" / "teacher_distilled_student_v1"
DEFAULT_MODEL_PATH = REPO_ROOT / "services" / "inference" / "models" / "teacher_distilled_clip_student_v1.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the teacher-distilled basketball student.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument(
        "--write-models",
        action="store_true",
        help="Persist the trained bundle to services/inference/models/ for runtime rollout.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_teacher_distilled_student_bundle(REPO_ROOT, output_dir=args.output_dir)
    if args.write_models:
        args.model_output.parent.mkdir(parents=True, exist_ok=True)
        result.bundle.save(args.model_output)

    summary = {
        "outputDir": str(args.output_dir),
        "modelOutput": str(args.model_output),
        "schemaVersion": result.manifest["schemaVersion"],
        "featureVersion": result.manifest["featureVersion"],
        "modelVersion": result.manifest["modelVersion"],
        "baselineMetrics": result.baseline_metrics,
        "distilledMetrics": result.distilled_metrics,
        "comparison": result.comparison,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(args.output_dir / "bundle.json")
    print(args.output_dir / "manifest.json")
    print(args.output_dir / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
