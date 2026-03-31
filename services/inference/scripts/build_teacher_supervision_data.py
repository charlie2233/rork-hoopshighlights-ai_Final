from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.datasets import build_teacher_supervision_bundle


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = build_teacher_supervision_bundle(
        repo_root=REPO_ROOT,
        output_dir=args.output_dir,
        min_teacher_confidence=args.min_teacher_confidence,
        min_hard_negative_confidence=args.min_hard_negative_confidence,
    )
    print(args.output_dir / "manifest.json")
    print(args.output_dir / "weights.json")
    print(args.output_dir / "all_records.jsonl")
    print(
        "records="
        f"{manifest['summary']['totalRecords']} "
        f"training_eligible={manifest['summary']['trainingEligibleRecords']} "
        f"calibration_anchor={manifest['summary']['calibrationAnchorRecords']}"
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build teacher supervision dataset splits and weights.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "teacher_supervision",
    )
    parser.add_argument("--min-teacher-confidence", type=float, default=0.82)
    parser.add_argument("--min-hard-negative-confidence", type=float, default=0.55)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
