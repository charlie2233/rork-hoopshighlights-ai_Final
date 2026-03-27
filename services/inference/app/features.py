from __future__ import annotations

import math
import subprocess
from pathlib import Path

from .interfaces import VideoFeatures


def extract_video_features(source_path: Path, *, sample_limit: int = 48) -> VideoFeatures:
    metadata = _probe_media(source_path)
    fps = metadata["fps"]
    duration_seconds = metadata["duration_seconds"]
    frame_count = int(metadata["frame_count"])

    frame_energy_profile: list[float] = []
    audio_energy_profile: list[float] = []

    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return VideoFeatures(
            source_path=source_path,
            duration_seconds=duration_seconds,
            fps=fps,
            frame_count=frame_count,
            frame_energy_profile=frame_energy_profile,
            audio_energy_profile=audio_energy_profile,
            metadata={**metadata, "opencv_available": False},
        )

    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        return VideoFeatures(
            source_path=source_path,
            duration_seconds=duration_seconds,
            fps=fps,
            frame_count=frame_count,
            frame_energy_profile=frame_energy_profile,
            audio_energy_profile=audio_energy_profile,
            metadata={**metadata, "opencv_available": True, "opened": False},
        )

    sample_count = min(max(int(math.ceil(duration_seconds)), 1), sample_limit)
    step = max(int(round(frame_count / sample_count)) if frame_count else int(round(max(fps, 1.0))), 1)
    previous_gray = None

    for index in range(sample_count):
        capture.set(cv2.CAP_PROP_POS_FRAMES, index * step)
        ok, frame = capture.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if previous_gray is None:
            motion = float(np.mean(gray)) / 255.0
        else:
            delta = cv2.absdiff(gray, previous_gray)
            motion = float(np.mean(delta)) / 255.0
        brightness = float(np.mean(gray)) / 255.0
        frame_energy_profile.append(min(max((0.65 * motion) + (0.35 * brightness), 0.0), 1.0))
        audio_energy_profile.append(min(max(motion * 0.55, 0.0), 1.0))
        previous_gray = gray

    capture.release()

    return VideoFeatures(
        source_path=source_path,
        duration_seconds=duration_seconds,
        fps=fps,
        frame_count=frame_count,
        frame_energy_profile=frame_energy_profile,
        audio_energy_profile=audio_energy_profile,
        metadata={**metadata, "opencv_available": True},
    )


def _probe_media(source_path: Path) -> dict[str, float]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate,r_frame_rate,duration,nb_frames",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(source_path),
    ]

    defaults = {"fps": 0.0, "duration_seconds": 0.0, "frame_count": 0.0}
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
        import json

        payload = json.loads(completed.stdout or "{}")
    except Exception:
        return defaults

    streams = payload.get("streams") or []
    stream = streams[0] if streams else {}
    format_info = payload.get("format") or {}

    duration = _coerce_float(format_info.get("duration"), 0.0)
    fps = _parse_fraction(stream.get("avg_frame_rate")) or _parse_fraction(stream.get("r_frame_rate")) or 0.0
    frame_count = int(_coerce_float(stream.get("nb_frames"), 0.0) or max(duration * max(fps, 0.0), 0.0))

    return {
        "fps": fps,
        "duration_seconds": max(duration, 0.0),
        "frame_count": float(max(frame_count, 0)),
    }


def _parse_fraction(value: object) -> float:
    if not isinstance(value, str) or "/" not in value:
        return 0.0
    numerator, denominator = value.split("/", 1)
    try:
        denom = float(denominator)
        if denom == 0:
            return 0.0
        return float(numerator) / denom
    except ValueError:
        return 0.0


def _coerce_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
