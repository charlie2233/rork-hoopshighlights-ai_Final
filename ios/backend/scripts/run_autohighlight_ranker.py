#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import sys
from pathlib import Path
from typing import Any, List


def main() -> int:
    parser = argparse.ArgumentParser(description="Run autohighlight rescoring and emit score boosts.")
    parser.add_argument("--repo", required=True, help="Path to the autohighlight checkout")
    parser.add_argument("--video", required=True, help="Path to the source video")
    parser.add_argument("--model", required=True, help="Path to the model file")
    parser.add_argument("--rate", type=int, default=75, help="Sampling interval in frames")
    args = parser.parse_args()

    request = _read_request()
    clips = request.get("clips") if isinstance(request, dict) else None
    if not isinstance(clips, list) or not clips:
        print(json.dumps({"boosts": []}))
        return 0

    repo_root = Path(args.repo).expanduser().resolve()
    video_path = Path(args.video).expanduser().resolve()
    model_path = Path(args.model).expanduser().resolve()
    if not repo_root.exists() or not video_path.exists() or not model_path.exists():
        print(json.dumps({"boosts": [0.0 for _ in clips]}))
        return 0

    sys.path.insert(0, str(repo_root))
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        from utils.event_detector import videoscan  # type: ignore
    except Exception:
        print(json.dumps({"boosts": [0.0 for _ in clips]}))
        return 0

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            predictions = videoscan(str(video_path), str(model_path), args.rate, verbose=False)
        except Exception:
            predictions = None

    if predictions is None:
        print(json.dumps({"boosts": [0.0 for _ in clips]}))
        return 0

    capture = cv2.VideoCapture(str(video_path))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    capture.release()
    step_seconds = max(args.rate / max(fps, 1.0), 0.1)

    boosts: List[float] = []
    for clip in clips:
        if not isinstance(clip, dict):
            boosts.append(0.0)
            continue
        start = _coerce_float(clip.get("startTime"), 0.0)
        end = max(start, _coerce_float(clip.get("endTime"), start))

        start_index = max(int(start / step_seconds), 0)
        end_index = max(start_index + 1, int(math.ceil(end / step_seconds)))
        segment = predictions[start_index:end_index]
        if getattr(segment, "size", 0) == 0:
            boosts.append(0.0)
            continue

        try:
            if segment.ndim == 1:
                score = float(segment.max())
            elif segment.shape[1] >= 3:
                score = float(max(segment[:, 1].max(), segment[:, 2].max()))
            else:
                score = float(segment.max())
        except Exception:
            score = 0.0

        boosts.append(round(max(0.0, min(score, 1.0)), 4))

    print(json.dumps({"boosts": boosts}))
    return 0


def _read_request() -> Any:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    raise SystemExit(main())
