from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.datasets.runtime_training import build_runtime_training_bundle


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = build_runtime_training_bundle(repo_root=REPO_ROOT, output_dir=args.output_dir)
    print(args.output_dir / "manifest.json")
    print(args.output_dir / "feature_names.json")
    print(f"records={manifest['summary']['totalRecords']} active={manifest['summary']['activeRecords']}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build runtime training splits and feature matrices.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "runtime_training",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())

