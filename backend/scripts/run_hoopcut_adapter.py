#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, List


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HoopCut detection and emit cloud clip JSON.")
    parser.add_argument("--repo", required=True, help="Path to the HoopCut_FH checkout")
    parser.add_argument("--video", required=True, help="Path to the source video")
    parser.add_argument("--min-clip", type=float, required=True)
    parser.add_argument("--max-clip", type=float, required=True)
    parser.add_argument("--max-clips", type=int, required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo).expanduser().resolve()
    main_root = repo_root / "main"
    video_path = Path(args.video).expanduser().resolve()
    if not main_root.exists() or not video_path.exists():
        print(json.dumps({"clips": []}))
        return 0

    sys.path.insert(0, str(main_root))
    try:
        import detector  # type: ignore
    except Exception:
        print(json.dumps({"clips": []}))
        return 0

    duration_seconds = _probe_duration(video_path)
    temp_root = Path(tempfile.mkdtemp(prefix="hoopcut-adapter-"))
    plot_dir = temp_root / "plots"
    debug_log = temp_root / "loop_debug.txt"

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            selected_points = detector.find_hoop(str(video_path), True)
            if not isinstance(selected_points, list) or len(selected_points) < 2:
                print(json.dumps({"clips": []}))
                return 0
            timestamps, make_miss = detector.detection_model(
                selected_points,
                str(video_path),
                str(plot_dir),
                str(debug_log),
                None,
            )
    except Exception:
        print(json.dumps({"clips": []}))
        return 0

    clips = _build_clips(
        timestamps=timestamps,
        make_miss=make_miss,
        duration_seconds=duration_seconds,
        min_clip_duration=args.min_clip,
        max_clip_duration=args.max_clip,
        max_clips=args.max_clips,
    )
    print(json.dumps({"clips": clips}))
    return 0


def _probe_duration(path: Path) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
        payload = json.loads(completed.stdout or "{}")
        return max(float(payload.get("format", {}).get("duration", 0.0)), 1.0)
    except Exception:
        return 60.0


def _build_clips(
    *,
    timestamps: Any,
    make_miss: Any,
    duration_seconds: float,
    min_clip_duration: float,
    max_clip_duration: float,
    max_clips: int,
) -> List[dict[str, Any]]:
    timestamp_values = list(timestamps) if timestamps is not None else []
    raw_timestamps = [float(value) for value in timestamp_values if _coerce_number(value) is not None]
    shot_times = raw_timestamps[1:] if len(raw_timestamps) > 1 and abs(raw_timestamps[0]) < 0.001 else raw_timestamps
    shot_times = sorted({round(time_value, 3) for time_value in shot_times if time_value >= 0.0})

    if not shot_times:
        return []

    outcomes = list(make_miss) if make_miss is not None else []
    base_span = min(max_clip_duration, max(min_clip_duration + 2.0, 5.0))
    pre_roll = min(base_span * 0.65, max_clip_duration * 0.7)
    post_roll = min(base_span - pre_roll, max_clip_duration - pre_roll)

    clips: list[dict[str, Any]] = []
    for index, shot_time in enumerate(shot_times):
        start = max(0.0, shot_time - pre_roll)
        end = min(duration_seconds, shot_time + post_roll)
        if end - start < min_clip_duration:
            end = min(duration_seconds, start + min_clip_duration)
        if end - start > max_clip_duration:
            end = min(duration_seconds, start + max_clip_duration)
        if end <= start:
            continue

        is_make = bool(outcomes[index]) if index < len(outcomes) else True
        label = "Made Shot" if is_make else "Missed Shot"
        combined = 0.9 if is_make else 0.78
        confidence = 0.9 if is_make else 0.72
        clips.append(
            {
                "startTime": round(start, 3),
                "endTime": round(end, 3),
                "confidence": round(confidence, 4),
                "label": label,
                "action": label,
                "audioScore": 0.58 if is_make else 0.46,
                "visualScore": 0.86,
                "motionScore": 0.74,
                "combinedScore": round(combined, 4),
                "detectionMethod": "cloud",
                "shouldAutoKeep": True,
                "shouldEnableSlowMotion": False,
            }
        )

    deduped = _dedupe(clips)
    deduped.sort(key=lambda clip: clip["combinedScore"], reverse=True)
    return deduped[:max_clips]


def _dedupe(clips: List[dict[str, Any]]) -> List[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for clip in sorted(clips, key=lambda item: (item["startTime"], -item["combinedScore"])):
        if any(_overlap_ratio(clip, existing) > 0.55 for existing in kept):
            continue
        kept.append(clip)
    return kept


def _overlap_ratio(left: dict[str, Any], right: dict[str, Any]) -> float:
    overlap = max(0.0, min(left["endTime"], right["endTime"]) - max(left["startTime"], right["startTime"]))
    if overlap <= 0.0:
        return 0.0
    shortest = min(
        max(left["endTime"] - left["startTime"], 0.001),
        max(right["endTime"] - right["startTime"], 0.001),
    )
    return overlap / shortest


def _coerce_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
