#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "ios" / "backend"))

from app.evaluation import DEFAULT_TIOU, evaluate_clip_rerank  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate HoopClips clip discovery and reranking quality.")
    parser.add_argument("--predictions", type=Path, help="JSON file with a predictions array.")
    parser.add_argument("--ground-truth", type=Path, help="JSON file with a groundTruth array.")
    parser.add_argument("--fixture", type=Path, help="JSON file containing both predictions and groundTruth arrays.")
    parser.add_argument("--tiou", type=float, default=DEFAULT_TIOU, help="Temporal IoU threshold for matching.")
    parser.add_argument("--k", type=int, nargs="*", default=[1, 3, 5], help="K values for Recall@K and Precision@K.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON only.")
    args = parser.parse_args()

    payload = load_payload(args)
    metrics = evaluate_clip_rerank(
        payload["predictions"],
        payload["groundTruth"],
        tiou_threshold=args.tiou,
        k_values=args.k,
    )

    if args.json:
        print(json.dumps(metrics, sort_keys=True))
    else:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


def load_payload(args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    if args.fixture:
        payload = json.loads(args.fixture.read_text(encoding="utf-8"))
        return {
            "predictions": list(payload.get("predictions", [])),
            "groundTruth": list(payload.get("groundTruth", payload.get("ground_truth", []))),
        }
    if args.predictions or args.ground_truth:
        if not args.predictions or not args.ground_truth:
            raise SystemExit("--predictions and --ground-truth must be provided together.")
        return {
            "predictions": list(json.loads(args.predictions.read_text(encoding="utf-8")).get("predictions", [])),
            "groundTruth": list(json.loads(args.ground_truth.read_text(encoding="utf-8")).get("groundTruth", [])),
        }
    return sample_payload()


def sample_payload() -> dict[str, list[dict[str, Any]]]:
    return {
        "groundTruth": [
            {"videoId": "sample", "startTime": 1.0, "endTime": 5.0, "label": "dunk", "teamId": "home"},
            {"videoId": "sample", "startTime": 10.0, "endTime": 14.0, "label": "steal", "teamId": "home"},
            {"videoId": "sample", "startTime": 18.0, "endTime": 23.0, "label": "three_pointer", "teamId": "home"},
        ],
        "predictions": [
            {"videoId": "sample", "startTime": 0.8, "endTime": 5.2, "label": "dunk", "score": 0.95, "teamId": "home"},
            {"videoId": "sample", "startTime": 9.5, "endTime": 13.6, "label": "steal", "score": 0.74, "teamId": "home"},
            {"videoId": "sample", "startTime": 18.3, "endTime": 22.7, "label": "three_pointer", "score": 0.81, "teamId": "home"},
            {"videoId": "sample", "startTime": 27.0, "endTime": 30.0, "label": "dunk", "score": 0.35, "reviewFeedbackTags": ["duplicate"]},
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
