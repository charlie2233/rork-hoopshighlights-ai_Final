from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.training.perception_supervision import build_perception_supervision_bundle


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = build_perception_supervision_bundle(repo_root=REPO_ROOT, output_dir=args.output_dir)
    print(args.output_dir / "manifest.json")
    print(args.output_dir / "feature_names.json")
    print(args.output_dir / "all_records.jsonl")
    print(
        "records="
        f"{manifest['summary']['totalRecords']} "
        f"active={manifest['summary']['activeRecords']} "
        f"calibration_anchor={manifest['summary']['calibrationAnchorRecords']}"
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build basketball perception supervision exports.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "perception_supervision",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
