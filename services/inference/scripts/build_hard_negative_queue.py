from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.datasets.hard_negative_mining import (
    build_hard_negative_report,
    load_live_payloads,
    write_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a hard-negative mining queue from live or shadow batch payloads.")
    parser.add_argument(
        "--input",
        required=True,
        nargs="+",
        help="One or more JSON files containing job payloads or clip arrays.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for the queue JSONL, training JSONL, markdown, and summary artifacts.",
    )
    parser.add_argument("--min-margin", type=float, default=0.08, help="Margin below which clips are treated as low-margin.")
    parser.add_argument(
        "--min-result-confidence",
        type=float,
        default=0.75,
        help="Result confidence below which clips receive an extra hard-negative boost.",
    )
    parser.add_argument("--top-k", type=int, default=None, help="Optional cap on the number of queued clips.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_paths = [Path(item) for item in args.input]
    clips = load_live_payloads(input_paths)
    report = build_hard_negative_report(
        clips,
        min_margin=args.min_margin,
        min_result_confidence=args.min_result_confidence,
        top_k=args.top_k,
    )
    queue_path, training_path, md_path = write_artifacts(Path(args.output_dir), report)
    print(md_path)
    print(queue_path)
    print(training_path)
    print(json.dumps(report.summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
