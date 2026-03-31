from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.datasets import (
    DEFAULT_MIN_TEACHER_CONFIDENCE,
    DEFAULT_SOURCE_DOMAINS,
    PSEUDO_LABEL_DATASET_VERSION,
    build_phase4_pseudo_label_bundle,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build phase4 pseudo-label artifacts from offline annotations.")
    parser.add_argument(
        "--input",
        nargs="*",
        default=None,
        help="Optional one or more annotation files (.json or .jsonl). Defaults to the seed gold and silver corpora.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "phase4_pseudo_labels",
        help="Directory for manifest and pseudo-label artifacts.",
    )
    parser.add_argument(
        "--min-teacher-confidence",
        type=float,
        default=DEFAULT_MIN_TEACHER_CONFIDENCE,
        help="Teacher confidence threshold required to retain a pseudo-label.",
    )
    parser.add_argument(
        "--source-domains",
        nargs="*",
        default=list(DEFAULT_SOURCE_DOMAINS),
        help="Allowed source-domain tags for the in-domain pseudo-label slice.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_paths = [Path(item) for item in args.input] if args.input else None
    manifest = build_phase4_pseudo_label_bundle(
        repo_root=REPO_ROOT,
        output_dir=args.output_dir,
        input_paths=input_paths,
        min_teacher_confidence=args.min_teacher_confidence,
        source_domains=args.source_domains,
    )
    print(args.output_dir / "manifest.json")
    print(args.output_dir / "all_records.jsonl")
    print(args.output_dir / "gold_anchor_records.jsonl")
    print(args.output_dir / "pseudo_label_records.jsonl")
    print(args.output_dir / "filtered_records.jsonl")
    print(
        f"datasetVersion={PSEUDO_LABEL_DATASET_VERSION} "
        f"totalRecords={manifest['summary']['totalRecords']} "
        f"pseudoLabelRecords={manifest['summary']['pseudoLabelRecords']} "
        f"goldAnchorRecords={manifest['summary']['goldAnchorRecords']}"
    )
    print(json.dumps(manifest["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
